import sys

from django.db.models.fields import FieldDoesNotExist
from django.db.models.loading import app_cache_ready

from mongoengine.fields import ReferenceField

#class PkWrapper(object):
#    """
#    Wraps an immutable class (like mongoengine's pk field) so that attributes can be added.
#    """
#    def __init__(self, baseObject):
#        self.__class__ = type(baseObject.__class__.__name__, (self.__class__, baseObject.__class__), {})
#        self.__dict__ = baseObject.__dict__

class PkWrapper(object):
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

class AdminOptions(object):
    """
    Used to store mongoengine's _meta dict to make the document admin
    as compatible as possible to django's meta class on models. 
    """
    def __init__(self, document):
        self.index_background = None
        self.collection = None
        self.queryset_class = None 
        self.allow_inheritance = None
        self.max_size = None
        self.ordering = None
        self.id_field = None
        self.indexes = None
        self.index_drop_dups = None
        self.unique_indexes = None
        self.app_label = None
        self.max_documents = None
        self.module_name = None
        self.index_opts = None
        self.verbose_name = None
        self.verbose_name_plural = None
        self.has_auto_field = False
        self.proxy = []
        self.parents = {}
        self.many_to_many = []
        
        self.document = document
        self.meta = document._meta
        
        self.init_from_meta()
        
        self.pk_name = self.id_field
        
        self.init_pk()
        
    def init_from_meta(self):
        for attr, value in self.document._meta.iteritems():
            if hasattr(self, attr):
                setattr(self, attr, value)
        
        try:
            self.object_name = self.document.__name__
        except AttributeError:
            self.object_name = self.document.__class__.__name__
            
        self.module_name = self.object_name.lower()
        
        model_module = sys.modules[self.document.__module__]
        self.app_label = model_module.__name__.split('.')[-2]
        
        if self.verbose_name is None:
            self.verbose_name = self.object_name
        
        self.verbose_name_raw = self.verbose_name
        
        if self.verbose_name_plural is None:
            self.verbose_name_plural = "%ss" % self.verbose_name
    
    @property    
    def pk(self):
        if not hasattr(self._pk, 'attname'):
            self.init_pk()
        return self._pk
            
            
    def init_pk(self):
        """
        Adds a wrapper around the documents pk field. The wrapper object gets the attributes
        django expects on the pk field, like name and attname.
        
        The function also adds a _get_pk_val method to the document.
        """
        if self.id_field is not None:
            try:
                pk_field = getattr(self.document, self.id_field)
                self._pk = PkWrapper(pk_field)
                self._pk.name = self.id_field
                self._pk.attname = self.id_field
                self._pk_name = self.id_field
                
                from mongoadmin.util import patch_document
                
                def _get_pk_val(self):
                    return self._pk_val
                
                patch_document(_get_pk_val, self.document)
                
                self.document._pk_val = getattr(self.document, self.pk_name)
            except AttributeError:
                return      
                
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

        Uses a cache internally, so after the first access, this is very fast.
        """
        try:
            try:
                return self._field_cache[name]
            except AttributeError:
                self._init_field_cache()
                return self._field_cache[name]
        except KeyError:
            raise FieldDoesNotExist('%s has no field named %r'
                    % (self.object_name, name))
            
        
    def _init_field_cache(self):
        if not hasattr(self, '_field_cache'):
            self._field_cache = {}
        
        for f in self.document._fields.itervalues():
            if isinstance(f, ReferenceField):
                model = f.document_type
                model._admin_opts = AdminOptions(model)
                self._field_cache[model._admin_opts.module_name] = (f, model, False, False)
            else:
                self._field_cache[f.name] = (f, None, True, False)
                
        return self._field_cache
         
    def get_field(self, name, many_to_many=True):
        """
        Returns the requested field by name. Raises FieldDoesNotExist on error.
        """
        return self.get_field_by_name(name)[0]

    def __getitem__(self, key):
        return self.meta[key]
    
    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default 
    
    def get_parent_list(self):
        return []
    
    def get_all_related_objects(self, local_only=False, include_hidden=False):
        return []

    def iteritems(self):
        return self.meta.iteritems()
