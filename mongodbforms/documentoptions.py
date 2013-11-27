import sys
from collections import MutableMapping
from types import MethodType

from django.db.models.fields import FieldDoesNotExist
from django.utils.text import capfirst
from django.db.models.options import get_verbose_name
from django.utils.functional import LazyObject
from django.conf import settings

from mongoengine.fields import ReferenceField, ListField


def patch_document(function, instance, bound=True):
    if bound:
        method = MethodType(function, instance)
    else:
        method = function
    setattr(instance, function.__name__, method)


def create_verbose_name(name):
    name = get_verbose_name(name)
    name = name.replace('_', ' ')
    return name


class Relation(object):
    # just an empty dict to make it useable with Django
    # mongoengine has no notion of this
    limit_choices_to = {}

    def __init__(self, to):
        self._to = to

    @property
    def to(self):
        if not isinstance(self._to._meta, (DocumentMetaWrapper, LazyDocumentMetaWrapper)):
            self._to._meta = DocumentMetaWrapper(self._to)
        return self._to

    @to.setter
    def to(self, value):
        self._to = value


class PkWrapper(object):
    editable = False
    fake = False
    
    def __init__(self, wrapped):
        self.obj = wrapped

    def __getattr__(self, attr):
        if attr in dir(self.obj):
            return getattr(self.obj, attr)
        raise AttributeError

    def __setattr__(self, attr, value):
        if attr != 'obj' and hasattr(self.obj, attr):
            setattr(self.obj, attr, value)
        super(PkWrapper, self).__setattr__(attr, value)


class LazyDocumentMetaWrapper(LazyObject):
    _document = None
    _meta = None
    
    def __init__(self, document):
        self._document = document
        self._meta = document._meta
        super(LazyDocumentMetaWrapper, self).__init__()
        
    def _setup(self):
        self._wrapped = DocumentMetaWrapper(self._document, self._meta)
        
    def __setattr__(self, name, value):
        if name in ["_document", "_meta",]:
            object.__setattr__(self, name, value)
        else:
            super(LazyDocumentMetaWrapper, self).__setattr__(name, value)
    
    def __dir__(self):
        return self._wrapped.__dir__()
    
    def __getitem__(self, key):
        return self._wrapped.__getitem__(key)
    
    def __setitem__(self, key, value):
        return self._wrapped.__getitem__(key, value)
        
    def __delitem__(self, key):
        return self._wrapped.__delitem__(key)
        
    def __len__(self):
        return self._wrapped.__len__()
        
    def __contains__(self, key):
        return self._wrapped.__contains__(key)
        

class DocumentMetaWrapper(MutableMapping):
    """
    Used to store mongoengine's _meta dict to make the document admin
    as compatible as possible to django's meta class on models.
    """
    # attributes Django deprecated. Not really sure when to remove them
    _deprecated_attrs = {'module_name': 'model_name'}

    pk = None
    pk_name = None
    _app_label = None
    model_name = None
    _verbose_name = None
    has_auto_field = False
    object_name = None
    proxy = []
    parents = {}
    many_to_many = []
    _field_cache = None
    document = None
    _meta = None
    concrete_model = None
    concrete_managers = []
    virtual_fields = []
    auto_created = False

    def __init__(self, document, meta=None):
        super(DocumentMetaWrapper, self).__init__()

        self.document = document
        # used by Django to distinguish between abstract and concrete models
        # here for now always the document
        self.concrete_model = document
        if meta is None:
            meta = getattr(document, '_meta', {})
            if isinstance(meta, LazyDocumentMetaWrapper):
                meta = meta._meta
        self._meta = meta

        try:
            self.object_name = self.document.__name__
        except AttributeError:
            self.object_name = self.document.__class__.__name__

        self.model_name = self.object_name.lower()

        # add the gluey stuff to the document and it's fields to make
        # everything play nice with Django
        self._setup_document_fields()
        # Setup self.pk if the document has an id_field in it's meta
        # if it doesn't have one it's an embedded document
        #if 'id_field' in self._meta:
        #    self.pk_name = self._meta['id_field']
        self._init_pk()

    def _setup_document_fields(self):
        for f in self.document._fields.values():
            # Yay, more glue. Django expects fields to have a couple attributes
            # at least in the admin, probably in more places.
            if not hasattr(f, 'rel'):
                # need a bit more for actual reference fields here
                if isinstance(f, ReferenceField):
                    f.rel = Relation(f.document_type)
                elif isinstance(f, ListField) and \
                        isinstance(f.field, ReferenceField):
                    f.field.rel = Relation(f.field.document_type)
                else:
                    f.rel = None
            if not hasattr(f, 'verbose_name') or f.verbose_name is None:
                f.verbose_name = capfirst(create_verbose_name(f.name))
            if not hasattr(f, 'flatchoices'):
                flat = []
                if f.choices is not None:
                    for choice, value in f.choices:
                        if isinstance(value, (list, tuple)):
                            flat.extend(value)
                        else:
                            flat.append((choice, value))
                f.flatchoices = flat
            if isinstance(f, ReferenceField) and not \
                    isinstance(f.document_type._meta, (DocumentMetaWrapper, LazyDocumentMetaWrapper)) and \
                    self.document != f.document_type:
                f.document_type._meta = LazyDocumentMetaWrapper(f.document_type)

    def _init_pk(self):
        """
        Adds a wrapper around the documents pk field. The wrapper object gets
        the attributes django expects on the pk field, like name and attname.

        The function also adds a _get_pk_val method to the document.
        """
        if 'id_field' in self._meta:
            self.pk_name = self._meta['id_field']
            pk_field = getattr(self.document, self.pk_name)
        else:
            pk_field = None
        self.pk = PkWrapper(pk_field)

        def _get_pk_val(self):
            return self._pk_val
        
        if pk_field is not None:
            self.pk.name = self.pk_name
            self.pk.attname = self.pk_name
            self.document._pk_val = pk_field
            patch_document(_get_pk_val, self.document)
        else:
            self.pk.fake = True
            # this is used in the admin and used to determine if the admin
            # needs to add a hidden pk field. It does not for embedded fields.
            # So we pretend to have an editable pk field and just ignore it otherwise
            self.pk.editable = True
    
    @property
    def app_label(self):
        if self._app_label is None:
            model_module = sys.modules[self.document.__module__]
            self._app_label = model_module.__name__.split('.')[-2]
        return self._app_label
            
    @property
    def verbose_name(self):
        """
        Returns the verbose name of the document.
        
        Checks the original meta dict first. If it is not found
        then generates a verbose name from the object name.
        """
        if self._verbose_name is None:
            verbose_name = self._meta.get('verbose_name', self.object_name)
            self._verbose_name = capfirst(create_verbose_name(verbose_name))
        return self._verbose_name
    
    @property
    def verbose_name_raw(self):
        return self.verbose_name
    
    @property
    def verbose_name_plural(self):
        return "%ss" % self.verbose_name
                
    def get_add_permission(self):
        return 'add_%s' % self.object_name.lower()

    def get_change_permission(self):
        return 'change_%s' % self.object_name.lower()

    def get_delete_permission(self):
        return 'delete_%s' % self.object_name.lower()
    
    def get_ordered_objects(self):
        return []
    
    def get_field_by_name(self, name):
        """
        Returns the (field_object, model, direct, m2m), where field_object is
        the Field instance for the given name, model is the model containing
        this field (None for local fields), direct is True if the field exists
        on this model, and m2m is True for many-to-many relations. When
        'direct' is False, 'field_object' is the corresponding RelatedObject
        for this field (since the field doesn't have an instance associated
        with it).
        """
        if name in self.document._fields:
            field = self.document._fields[name]
            if isinstance(field, ReferenceField):
                return (field, field.document_type, False, False)
            else:
                return (field, None, True, False)
        else:
            raise FieldDoesNotExist('%s has no field named %r' %
                                    (self.object_name, name))
         
    def get_field(self, name, many_to_many=True):
        """
        Returns the requested field by name. Raises FieldDoesNotExist on error.
        """
        return self.get_field_by_name(name)[0]
    
    @property
    def swapped(self):
        """
        Has this model been swapped out for another? If so, return the model
        name of the replacement; otherwise, return None.

        For historical reasons, model name lookups using get_model() are
        case insensitive, so we make sure we are case insensitive here.
        
        NOTE: Not sure this is actually usefull for documents. So at the
        moment it's really only here because the admin wants it. It might
        prove usefull for someone though, so it's more then just a dummy.
        """
        if self._meta.get('swappable', False):
            model_label = '%s.%s' % (self.app_label, self.object_name.lower())
            swapped_for = getattr(settings, self.swappable, None)
            if swapped_for:
                try:
                    swapped_label, swapped_object = swapped_for.split('.')
                except ValueError:
                    # setting not in the format app_label.model_name
                    # raising ImproperlyConfigured here causes problems with
                    # test cleanup code - instead it is raised in
                    # get_user_model or as part of validation.
                    return swapped_for

                if '%s.%s' % (swapped_label, swapped_object.lower()) \
                        not in (None, model_label):
                    return swapped_for
        return None
    
    def __getattr__(self, name):
        if name in self._deprecated_attrs:
            return getattr(self, self._deprecated_attrs.get(name))
            
        try:
            return self._meta[name]
        except KeyError:
            raise AttributeError
                    
    def __setattr__(self, name, value):
        if not hasattr(self, name):
            self._meta[name] = value
        else:
            super(DocumentMetaWrapper, self).__setattr__(name, value)
    
    def __contains__(self, key):
        return key in self._meta
    
    def __getitem__(self, key):
        return self._meta[key]
    
    def __setitem__(self, key, value):
        self._meta[key] = value

    def __delitem__(self, key):
        return self._meta.__delitem__(key)

    def __iter__(self):
        return self._meta.__iter__()

    def __len__(self):
        return self._meta.__len__()

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default
    
    def get_parent_list(self):
        return []
    
    def get_all_related_objects(self, *args, **kwargs):
        return []

    def iteritems(self):
        return iter(self._meta.items())
