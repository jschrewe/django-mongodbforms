import os
import itertools
from collections import Callable, OrderedDict
from functools import reduce

from django.forms.forms import (BaseForm, DeclarativeFieldsMetaclass,
                                NON_FIELD_ERRORS, pretty_name)
from django.forms.widgets import media_property
from django.core.exceptions import FieldError
from django.core.validators import EMPTY_VALUES
from django.forms.util import ErrorList
from django.forms.formsets import BaseFormSet, formset_factory
from django.utils.translation import ugettext_lazy as _, ugettext
from django.utils.text import capfirst, get_valid_filename

from mongoengine.fields import (ObjectIdField, ListField, ReferenceField,
                                FileField, MapField, EmbeddedDocumentField)
try:
    from mongoengine.base import ValidationError
except ImportError:
    from mongoengine.errors import ValidationError
from mongoengine.queryset import OperationError, Q
from mongoengine.queryset.base import BaseQuerySet
from mongoengine.connection import get_db, DEFAULT_CONNECTION_NAME
from mongoengine.base import NON_FIELD_ERRORS as MONGO_NON_FIELD_ERRORS

from gridfs import GridFS

from mongodbforms.documentoptions import DocumentMetaWrapper
from mongodbforms.util import with_metaclass, load_field_generator

_fieldgenerator = load_field_generator()


def _get_unique_filename(name, db_alias=DEFAULT_CONNECTION_NAME,
                         collection_name='fs'):
    fs = GridFS(get_db(db_alias), collection_name)
    file_root, file_ext = os.path.splitext(get_valid_filename(name))
    count = itertools.count(1)
    while fs.exists(filename=name):
        # file_ext includes the dot.
        name = os.path.join("%s_%s%s" % (file_root, next(count), file_ext))
    return name


def _save_iterator_file(field, instance, uploaded_file, file_data=None):
    """
    Takes care of saving a file for a list field. Returns a Mongoengine
    fileproxy object or the file field.
    """
    # for a new file we need a new proxy object
    if file_data is None:
        file_data = field.field.get_proxy_obj(key=field.name,
                                              instance=instance)

    if file_data.instance is None:
        file_data.instance = instance
    if file_data.key is None:
        file_data.key = field.name

    if file_data.grid_id:
        file_data.delete()

    uploaded_file.seek(0)
    filename = _get_unique_filename(uploaded_file.name, field.field.db_alias,
                                    field.field.collection_name)
    file_data.put(uploaded_file, content_type=uploaded_file.content_type,
                  filename=filename)
    file_data.close()

    return file_data


def construct_instance(form, instance, fields=None, exclude=None):
    """
    Constructs and returns a document instance from the bound ``form``'s
    ``cleaned_data``, but does not save the returned instance to the
    database.
    """
    cleaned_data = form.cleaned_data
    file_field_list = []

    # check wether object is instantiated
    if isinstance(instance, type):
        instance = instance()

    for f in instance._fields.values():
        if isinstance(f, ObjectIdField):
            continue
        if f.name not in cleaned_data:
            continue
        if fields is not None and f.name not in fields:
            continue
        if exclude and f.name in exclude:
            continue
        # Defer saving file-type fields until after the other fields, so a
        # callable upload_to can use the values from other fields.
        if isinstance(f, FileField) or \
                (isinstance(f, (MapField, ListField)) and
                 isinstance(f.field, FileField)):
            file_field_list.append(f)
        else:
            setattr(instance, f.name, cleaned_data.get(f.name))

    for f in file_field_list:
        if isinstance(f, MapField):
            map_field = getattr(instance, f.name)
            uploads = cleaned_data[f.name]
            for key, uploaded_file in uploads.items():
                if uploaded_file is None:
                    continue
                file_data = map_field.get(key, None)
                map_field[key] = _save_iterator_file(f, instance,
                                                     uploaded_file, file_data)
            setattr(instance, f.name, map_field)
        elif isinstance(f, ListField):
            list_field = getattr(instance, f.name)
            uploads = cleaned_data[f.name]
            for i, uploaded_file in enumerate(uploads):
                if uploaded_file is None:
                    continue
                try:
                    file_data = list_field[i]
                except IndexError:
                    file_data = None
                file_obj = _save_iterator_file(f, instance,
                                               uploaded_file, file_data)
                try:
                    list_field[i] = file_obj
                except IndexError:
                    list_field.append(file_obj)
            setattr(instance, f.name, list_field)
        else:
            field = getattr(instance, f.name)
            upload = cleaned_data[f.name]
            if upload is None:
                continue

            try:
                upload.file.seek(0)
                # delete first to get the names right
                if field.grid_id:
                    field.delete()
                filename = _get_unique_filename(upload.name, f.db_alias,
                                                f.collection_name)
                field.put(upload, content_type=upload.content_type,
                          filename=filename)
                setattr(instance, f.name, field)
            except AttributeError:
                # file was already uploaded and not changed during edit.
                # upload is already the gridfsproxy object we need.
                upload.get()
                setattr(instance, f.name, upload)

    return instance


def save_instance(form, instance, fields=None, fail_message='saved',
                  commit=True, exclude=None, construct=True):
    """
    Saves bound Form ``form``'s cleaned_data into document ``instance``.

    If commit=True, then the changes to ``instance`` will be saved to the
    database. Returns ``instance``.

    If construct=False, assume ``instance`` has already been constructed and
    just needs to be saved.
    """
    if construct:
        instance = construct_instance(form, instance, fields, exclude)

    if form.errors:
        raise ValueError("The %s could not be %s because the data didn't"
                         " validate." % (instance.__class__.__name__,
                                         fail_message))

    if commit and hasattr(instance, 'save'):
        # see BaseDocumentForm._post_clean for an explanation
        # if len(form._meta._dont_save) > 0:
        #    data = instance._data
        #    new_data = dict([(n, f) for n, f in data.items() if not n \
        #                    in form._meta._dont_save])
        #    instance._data = new_data
        #    instance.save()
        #    instance._data = data
        # else:
        instance.save()
    return instance


def document_to_dict(instance, fields=None, exclude=None):
    """
    Returns a dict containing the data in ``instance`` suitable for passing as
    a Form's ``initial`` keyword argument.

    ``fields`` is an optional list of field names. If provided, only the named
    fields will be included in the returned dict.

    ``exclude`` is an optional list of field names. If provided, the named
    fields will be excluded from the returned dict, even if they are listed in
    the ``fields`` argument.
    """
    data = {}
    for f in instance._fields.values():
        if fields and f.name not in fields:
            continue
        if exclude and f.name in exclude:
            continue
        data[f.name] = getattr(instance, f.name, '')
    return data


def fields_for_document(document, fields=None, exclude=None, widgets=None,
                        formfield_callback=None,
                        field_generator=_fieldgenerator):
    """
    Returns a ``SortedDict`` containing form fields for the given model.

    ``fields`` is an optional list of field names. If provided, only the named
    fields will be included in the returned fields.

    ``exclude`` is an optional list of field names. If provided, the named
    fields will be excluded from the returned fields, even if they are listed
    in the ``fields`` argument.
    """
    field_list = []
    if isinstance(field_generator, type):
        field_generator = field_generator()

    if formfield_callback and not isinstance(formfield_callback, Callable):
        raise TypeError('formfield_callback must be a function or callable')

    for name in document._fields_ordered:
        f = document._fields.get(name)
        if isinstance(f, ObjectIdField):
            continue
        if fields and f.name not in fields:
            continue
        if exclude and f.name in exclude:
            continue
        if widgets and f.name in widgets:
            kwargs = {'widget': widgets[f.name]}
        else:
            kwargs = {}

        if formfield_callback:
            formfield = formfield_callback(f, **kwargs)
        else:
            formfield = field_generator.generate(f, **kwargs)

        if formfield:
            field_list.append((f.name, formfield))

    field_dict = OrderedDict(field_list)
    if fields:
        field_dict = OrderedDict(
            [(f, field_dict.get(f)) for f in fields
                if ((not exclude) or (exclude and f not in exclude))]
        )

    return field_dict


class ModelFormOptions(object):

    def __init__(self, options=None):
        # document class can be declared with 'document =' or 'model ='
        self.document = getattr(options, 'document', None)
        if self.document is None:
            self.document = getattr(options, 'model', None)

        self.model = self.document
        meta = getattr(self.document, '_meta', {})
        # set up the document meta wrapper if document meta is a dict
        if self.document is not None and \
                not isinstance(meta, DocumentMetaWrapper):
            self.document._meta = DocumentMetaWrapper(self.document)
        self.fields = getattr(options, 'fields', None)
        self.exclude = getattr(options, 'exclude', None)
        self.widgets = getattr(options, 'widgets', None)
        self.embedded_field = getattr(options, 'embedded_field_name', None)
        self.formfield_generator = getattr(options, 'formfield_generator',
                                           _fieldgenerator)

        self._dont_save = []

        self.labels = getattr(options, 'labels', None)
        self.help_texts = getattr(options, 'help_texts', None)


class DocumentFormMetaclass(DeclarativeFieldsMetaclass):
    def __new__(cls, name, bases, attrs):
        formfield_callback = attrs.pop('formfield_callback', None)
        try:
            parents = [
                b for b in bases
                if issubclass(b, DocumentForm) or
                issubclass(b, EmbeddedDocumentForm)
            ]
        except NameError:
            # We are defining DocumentForm itself.
            parents = None
        new_class = super(DocumentFormMetaclass, cls).__new__(cls, name,
                                                              bases, attrs)
        if not parents:
            return new_class

        if 'media' not in attrs:
            new_class.media = media_property(new_class)

        opts = new_class._meta = ModelFormOptions(
            getattr(new_class, 'Meta', None)
        )
        if opts.document:
            formfield_generator = getattr(opts,
                                          'formfield_generator',
                                          _fieldgenerator)

            # If a model is defined, extract form fields from it.
            fields = fields_for_document(opts.document, opts.fields,
                                         opts.exclude, opts.widgets,
                                         formfield_callback,
                                         formfield_generator)
            # make sure opts.fields doesn't specify an invalid field
            none_document_fields = [k for k, v in fields.items() if not v]
            missing_fields = (set(none_document_fields) -
                              set(new_class.declared_fields.keys()))
            if missing_fields:
                message = 'Unknown field(s) (%s) specified for %s'
                message = message % (', '.join(missing_fields),
                                     opts.model.__name__)
                raise FieldError(message)
            # Override default model fields with any custom declared ones
            # (plus, include all the other declared fields).
            fields.update(new_class.declared_fields)
        else:
            fields = new_class.declared_fields

        new_class.base_fields = fields
        return new_class


class BaseDocumentForm(BaseForm):

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None,
                 initial=None, error_class=ErrorList, label_suffix=':',
                 empty_permitted=False, instance=None):

        opts = self._meta

        if instance is None:
            if opts.document is None:
                raise ValueError('A document class must be provided.')
            # if we didn't get an instance, instantiate a new one
            self.instance = opts.document
            object_data = {}
        else:
            self.instance = instance
            object_data = document_to_dict(instance, opts.fields, opts.exclude)

        # if initial was provided, it should override the values from instance
        if initial is not None:
            object_data.update(initial)

        # self._validate_unique will be set to True by BaseModelForm.clean().
        # It is False by default so overriding self.clean() and failing to call
        # super will stop validate_unique from being called.
        self._validate_unique = False
        super(BaseDocumentForm, self).__init__(data, files, auto_id, prefix,
                                               object_data, error_class,
                                               label_suffix, empty_permitted)

    def _update_errors(self, message_dict):
        for k, v in list(message_dict.items()):
            if k != NON_FIELD_ERRORS:
                self._errors.setdefault(k, self.error_class()).extend(v)
                # Remove the invalid data from the cleaned_data dict
                if k in self.cleaned_data:
                    del self.cleaned_data[k]
        if NON_FIELD_ERRORS in message_dict:
            messages = message_dict[NON_FIELD_ERRORS]
            self._errors.setdefault(NON_FIELD_ERRORS,
                                    self.error_class()).extend(messages)

    def _get_validation_exclusions(self):
        """
        For backwards-compatibility, several types of fields need to be
        excluded from model validation. See the following tickets for
        details: #12507, #12521, #12553
        """
        exclude = []
        # Build up a list of fields that should be excluded from model field
        # validation and unique checks.
        for f in self.instance._fields.values():
            # Exclude fields that aren't on the form. The developer may be
            # adding these values to the model after form validation.
            if f.name not in self.fields:
                exclude.append(f.name)

            # Don't perform model validation on fields that were defined
            # manually on the form and excluded via the ModelForm's Meta
            # class. See #12901.
            elif self._meta.fields and f.name not in self._meta.fields:
                exclude.append(f.name)
            elif self._meta.exclude and f.name in self._meta.exclude:
                exclude.append(f.name)

            # Exclude fields that failed form validation. There's no need for
            # the model fields to validate them as well.
            elif f.name in list(self._errors.keys()):
                exclude.append(f.name)

            # Exclude empty fields that are not required by the form, if the
            # underlying model field is required. This keeps the model field
            # from raising a required error. Note: don't exclude the field from
            # validaton if the model field allows blanks. If it does, the blank
            # value may be included in a unique check, so cannot be excluded
            # from validation.
            else:
                field_value = self.cleaned_data.get(f.name, None)
                if not f.required and field_value in EMPTY_VALUES:
                    exclude.append(f.name)
        return exclude

    def clean(self):
        self._validate_unique = True
        return self.cleaned_data

    def _post_clean(self):
        opts = self._meta

        # Update the model instance with self.cleaned_data.
        self.instance = construct_instance(self, self.instance, opts.fields,
                                           opts.exclude)
        changed_fields = getattr(self.instance, '_changed_fields', [])

        exclude = self._get_validation_exclusions()
        try:
            for f in self.instance._fields.values():
                value = getattr(self.instance, f.name)
                if f.name not in exclude:
                    f.validate(value)
                elif value in EMPTY_VALUES and f.name not in changed_fields:
                    # mongoengine chokes on empty strings for fields
                    # that are not required. Clean them up here, though
                    # this is maybe not the right place :-)
                    setattr(self.instance, f.name, None)
                    # opts._dont_save.append(f.name)
        except ValidationError as e:
            err = {f.name: [e.message]}
            self._update_errors(err)

        # Call validate() on the document. Since mongoengine
        # does not provide an argument to specify which fields
        # should be excluded during validation, we replace
        # instance._fields_ordered with a version that does
        # not include excluded fields. The attribute gets
        # restored after validation.
        original_fields = self.instance._fields_ordered
        self.instance._fields_ordered = tuple(
            [f for f in original_fields if f not in exclude]
        )
        try:
            self.instance.validate()
        except ValidationError as e:
            if MONGO_NON_FIELD_ERRORS in e.errors:
                error = e.errors.get(MONGO_NON_FIELD_ERRORS)
            else:
                error = e.message
            self._update_errors({NON_FIELD_ERRORS: [error, ]})
        finally:
            self.instance._fields_ordered = original_fields

        # Validate uniqueness if needed.
        if self._validate_unique:
            self.validate_unique()

    def validate_unique(self):
        """
        Validates unique constrains on the document.
        unique_with is supported now.
        """
        errors = []
        exclude = self._get_validation_exclusions()
        for f in self.instance._fields.values():
            if f.unique and f.name not in exclude:
                filter_kwargs = {
                    f.name: getattr(self.instance, f.name),
                    'q_obj': None,
                }
                if f.unique_with:
                    for u_with in f.unique_with:
                        u_with_field = self.instance._fields[u_with]
                        u_with_attr = getattr(self.instance, u_with)
                        # handling ListField(ReferenceField()) sucks big time
                        # What we need to do is construct a Q object that
                        # queries for the pk of every list entry and only
                        # accepts lists with the same length as our list
                        if isinstance(u_with_field, ListField) and \
                                isinstance(u_with_field.field, ReferenceField):
                            q_list = [Q(**{u_with: k.pk}) for k in u_with_attr]
                            q = reduce(lambda x, y: x & y, q_list)
                            size_key = '%s__size' % u_with
                            q = q & Q(**{size_key: len(u_with_attr)})
                            filter_kwargs['q_obj'] = q & filter_kwargs['q_obj']
                        else:
                            filter_kwargs[u_with] = u_with_attr
                qs = self.instance.__class__.objects.clone()
                qs = qs.no_dereference().filter(**filter_kwargs)
                # Exclude the current object from the query if we are editing
                # an instance (as opposed to creating a new one)
                if self.instance.pk is not None:
                    qs = qs.filter(pk__ne=self.instance.pk)
                if qs.count() > 0:
                    message = _("%s with this %s already exists.") % (
                        str(capfirst(self.instance._meta.verbose_name)),
                        str(pretty_name(f.name))
                    )
                    err_dict = {f.name: [message]}
                    self._update_errors(err_dict)
                    errors.append(err_dict)

        return errors

    def save(self, commit=True):
        """
        Saves this ``form``'s cleaned_data into model instance
        ``self.instance``.

        If commit=True, then the changes to ``instance`` will be saved to the
        database. Returns ``instance``.
        """
        try:
            if self.instance.pk is None:
                fail_message = 'created'
            else:
                fail_message = 'changed'
        except (KeyError, AttributeError):
            fail_message = 'embedded document saved'
        obj = save_instance(self, self.instance, self._meta.fields,
                            fail_message, commit, construct=False)

        return obj
    save.alters_data = True


class DocumentForm(with_metaclass(DocumentFormMetaclass, BaseDocumentForm)):
    pass


def documentform_factory(document, form=DocumentForm, fields=None,
                         exclude=None, formfield_callback=None):
    # Build up a list of attributes that the Meta object will have.
    attrs = {'document': document, 'model': document}
    if fields is not None:
        attrs['fields'] = fields
    if exclude is not None:
        attrs['exclude'] = exclude

    # If parent form class already has an inner Meta, the Meta we're
    # creating needs to inherit from the parent's inner meta.
    parent = (object,)
    if hasattr(form, 'Meta'):
        parent = (form.Meta, object)
    Meta = type('Meta', parent, attrs)

    # Give this new form class a reasonable name.
    if isinstance(document, type):
        doc_inst = document()
    else:
        doc_inst = document
    class_name = doc_inst.__class__.__name__ + 'Form'

    # Class attributes for the new form class.
    form_class_attrs = {
        'Meta': Meta,
        'formfield_callback': formfield_callback
    }

    return DocumentFormMetaclass(class_name, (form,), form_class_attrs)


class EmbeddedDocumentForm(with_metaclass(DocumentFormMetaclass,
                                          BaseDocumentForm)):

    def __init__(self, parent_document, data=None, files=None, position=None,
                 *args, **kwargs):
        if self._meta.embedded_field is not None and \
                self._meta.embedded_field not in parent_document._fields:
            raise FieldError("Parent document must have field %s" %
                             self._meta.embedded_field)

        instance = kwargs.pop('instance', None)

        if isinstance(parent_document._fields.get(self._meta.embedded_field),
                      ListField):
            # if we received a list position of the instance and no instance
            # load the instance from the parent document and proceed as normal
            if instance is None and position is not None:
                instance = getattr(parent_document,
                                   self._meta.embedded_field)[position]

            # same as above only the other way around. Note: Mongoengine
            # defines equality as having the same data, so if you have 2
            # objects with the same data the first one will be edited. That
            # may or may not be the right one.
            if instance is not None and position is None:
                emb_list = getattr(parent_document, self._meta.embedded_field)
                position = next(
                    (i for i, obj in enumerate(emb_list) if obj == instance),
                    None
                )

        super(EmbeddedDocumentForm, self).__init__(data=data, files=files,
                                                   instance=instance, *args,
                                                   **kwargs)
        self.parent_document = parent_document
        self.position = position

    def save(self, commit=True):
        """If commit is True the embedded document is added to the parent
        document. Otherwise the parent_document is left untouched and the
        embedded is returned as usual.
        """
        if self.errors:
            raise ValueError("The %s could not be saved because the data"
                             "didn't validate." %
                             self.instance.__class__.__name__)

        if commit:
            field = self.parent_document._fields.get(self._meta.embedded_field)
            if isinstance(field, ListField) and self.position is None:
                # no position given, simply appending to ListField
                try:
                    self.parent_document.update(**{
                        "push__" + self._meta.embedded_field: self.instance
                    })
                except:
                    raise OperationError("The %s could not be appended." %
                                         self.instance.__class__.__name__)
            elif isinstance(field, ListField) and self.position is not None:
                # updating ListField at given position
                try:
                    self.parent_document.update(**{
                        "__".join(("set", self._meta.embedded_field,
                                   str(self.position))): self.instance
                    })
                except:
                    raise OperationError("The %s could not be updated at "
                                         "position %d." %
                                         (self.instance.__class__.__name__,
                                          self.position))
            else:
                # not a listfield on parent, treat as an embedded field
                setattr(self.parent_document, self._meta.embedded_field,
                        self.instance)
                self.parent_document.save()
        return self.instance


class BaseDocumentFormSet(BaseFormSet):

    """
    A ``FormSet`` for editing a queryset and/or adding new objects to it.
    """

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None,
                 queryset=[], **kwargs):
        if not isinstance(queryset, (list, BaseQuerySet)):
            queryset = [queryset]
        self.queryset = queryset
        self.initial = self.construct_initial()
        defaults = {'data': data, 'files': files, 'auto_id': auto_id,
                    'prefix': prefix, 'initial': self.initial}
        defaults.update(kwargs)
        super(BaseDocumentFormSet, self).__init__(**defaults)

    def construct_initial(self):
        initial = []
        try:
            for d in self.get_queryset():
                initial.append(document_to_dict(d))
        except TypeError:
            pass
        return initial

    def initial_form_count(self):
        """Returns the number of forms that are required in this FormSet."""
        if not (self.data or self.files):
            return len(self.get_queryset())
        return super(BaseDocumentFormSet, self).initial_form_count()

    def get_queryset(self):
        qs = self.queryset or []
        return qs

    def save_object(self, form):
        obj = form.save(commit=False)
        return obj

    def save(self, commit=True):
        """
        Saves model instances for every form, adding and changing instances
        as necessary, and returns the list of instances.
        """
        saved = []
        for form in self.forms:
            if not form.has_changed() and form not in self.initial_forms:
                continue
            obj = self.save_object(form)
            if form.cleaned_data.get("DELETE", False):
                try:
                    obj.delete()
                except AttributeError:
                    # if it has no delete method it is an embedded object. We
                    # just don't add to the list and it's gone. Cool huh?
                    continue
            if commit:
                obj.save()
            saved.append(obj)
        return saved

    def clean(self):
        self.validate_unique()

    def validate_unique(self):
        errors = []
        for form in self.forms:
            if not hasattr(form, 'cleaned_data'):
                continue
            errors += form.validate_unique()

        if errors:
            raise ValidationError(errors)

    def get_date_error_message(self, date_check):
        return ugettext("Please correct the duplicate data for %(field_name)s "
                        "which must be unique for the %(lookup)s "
                        "in %(date_field)s.") % {
            'field_name': date_check[2],
            'date_field': date_check[3],
            'lookup': str(date_check[1]),
        }

    def get_form_error(self):
        return ugettext("Please correct the duplicate values below.")


def documentformset_factory(document, form=DocumentForm,
                            formfield_callback=None,
                            formset=BaseDocumentFormSet,
                            extra=1, can_delete=False, can_order=False,
                            max_num=None, fields=None, exclude=None):
    """
    Returns a FormSet class for the given Django model class.
    """
    form = documentform_factory(document, form=form, fields=fields,
                                exclude=exclude,
                                formfield_callback=formfield_callback)
    FormSet = formset_factory(form, formset, extra=extra, max_num=max_num,
                              can_order=can_order, can_delete=can_delete)
    FormSet.model = document
    FormSet.document = document
    return FormSet


class BaseInlineDocumentFormSet(BaseDocumentFormSet):

    """
    A formset for child objects related to a parent.

    self.instance -> the document containing the inline objects
    """

    def __init__(self, data=None, files=None, instance=None,
                 save_as_new=False, prefix=None, queryset=[], **kwargs):
        self.instance = instance
        self.save_as_new = save_as_new

        super(BaseInlineDocumentFormSet, self).__init__(data, files,
                                                        prefix=prefix,
                                                        queryset=queryset,
                                                        **kwargs)

    def initial_form_count(self):
        if self.save_as_new:
            return 0
        return super(BaseInlineDocumentFormSet, self).initial_form_count()

    # @classmethod
    def get_default_prefix(cls):
        return cls.document.__name__.lower()
    get_default_prefix = classmethod(get_default_prefix)

    def add_fields(self, form, index):
        super(BaseInlineDocumentFormSet, self).add_fields(form, index)

        # Add the generated field to form._meta.fields if it's defined to make
        # sure validation isn't skipped on that field.
        if form._meta.fields:
            if isinstance(form._meta.fields, tuple):
                form._meta.fields = list(form._meta.fields)
            # form._meta.fields.append(self.fk.name)

    def get_unique_error_message(self, unique_check):
        unique_check = [
            field for field in unique_check if field != self.fk.name
        ]
        return super(BaseInlineDocumentFormSet, self).get_unique_error_message(
            unique_check
        )


def inlineformset_factory(document, form=DocumentForm,
                          formset=BaseInlineDocumentFormSet,
                          fields=None, exclude=None,
                          extra=1, can_order=False, can_delete=True,
                          max_num=None, formfield_callback=None):
    """
    Returns an ``InlineFormSet`` for the given kwargs.

    You must provide ``fk_name`` if ``model`` has more than one ``ForeignKey``
    to ``parent_model``.
    """
    kwargs = {
        'form': form,
        'formfield_callback': formfield_callback,
        'formset': formset,
        'extra': extra,
        'can_delete': can_delete,
        'can_order': can_order,
        'fields': fields,
        'exclude': exclude,
        'max_num': max_num,
    }
    FormSet = documentformset_factory(document, **kwargs)
    return FormSet


class EmbeddedDocumentFormSet(BaseDocumentFormSet):

    def __init__(self, data=None, files=None, save_as_new=False,
                 prefix=None, queryset=[], parent_document=None, **kwargs):

        if parent_document is not None:
            self.parent_document = parent_document

        if 'instance' in kwargs:
            instance = kwargs.pop('instance')
            if parent_document is None:
                self.parent_document = instance

        queryset = getattr(self.parent_document, self.form._meta.embedded_field)
        if not isinstance(queryset, list) and queryset is None:
            queryset = []
        elif not isinstance(queryset, list):
            queryset = [queryset, ]

        super(EmbeddedDocumentFormSet, self).__init__(data, files, save_as_new,
                                                      prefix, queryset,
                                                      **kwargs)

    def _construct_form(self, i, **kwargs):
        defaults = {'parent_document': self.parent_document}

        # add position argument to the form. Otherwise we will spend
        # a huge amount of time iterating over the list field on form __init__
        emb_list = getattr(self.parent_document,
                           self.form._meta.embedded_field)

        if emb_list is not None and len(emb_list) > i:
            defaults['position'] = i
        defaults.update(kwargs)

        form = super(EmbeddedDocumentFormSet, self)._construct_form(
            i, **defaults)
        return form

    @classmethod
    def get_default_prefix(cls):
        return cls.document.__name__.lower()

    @property
    def empty_form(self):
        form = self.form(
            self.parent_document,
            auto_id=self.auto_id,
            prefix=self.add_prefix('__prefix__'),
            empty_permitted=True,
        )
        self.add_fields(form, None)
        return form

    def save(self, commit=True):
        # Don't try to save the new documents. Embedded objects don't have
        # a save method anyway.
        objs = super(EmbeddedDocumentFormSet, self).save(commit=False)
        objs = objs or []

        if commit and self.parent_document is not None:
            field = self.parent_document._fields.get(
                self.form._meta.embedded_field, None)
            if isinstance(field, EmbeddedDocumentField):
                try:
                    obj = objs[0]
                except IndexError:
                    obj = None
                setattr(
                    self.parent_document, self.form._meta.embedded_field, obj)
            else:
                setattr(
                    self.parent_document, self.form._meta.embedded_field, objs)
            self.parent_document.save()

        return objs


def _get_embedded_field(parent_doc, document, emb_name=None, can_fail=False):
    if emb_name:
        emb_fields = [
            f for f in parent_doc._fields.values() if f.name == emb_name]
        if len(emb_fields) == 1:
            field = emb_fields[0]
            if not isinstance(field, (EmbeddedDocumentField, ListField)) or \
                (isinstance(field, EmbeddedDocumentField) and
                    field.document_type != document) or \
                (isinstance(field, ListField) and
                    isinstance(field.field, EmbeddedDocumentField) and
                    field.field.document_type != document):
                raise Exception(
                    "emb_name '%s' is not a EmbeddedDocumentField or not a ListField to %s" % (
                        emb_name, document
                    )
                )
            elif len(emb_fields) == 0:
                raise Exception("%s has no field named '%s'" %
                                (parent_doc, emb_name))
    else:
        emb_fields = [
            f for f in parent_doc._fields.values()
            if (isinstance(field, EmbeddedDocumentField) and
                field.document_type == document) or
               (isinstance(field, ListField) and
                isinstance(field.field, EmbeddedDocumentField) and
                field.field.document_type == document)
        ]
        if len(emb_fields) == 1:
            field = emb_fields[0]
        elif len(emb_fields) == 0:
            if can_fail:
                return
            raise Exception(
                "%s has no EmbeddedDocumentField or ListField to %s" % (parent_doc, document))
        else:
            raise Exception(
                "%s has more than 1 EmbeddedDocumentField to %s" % (parent_doc, document))

    return field


def embeddedformset_factory(document, parent_document,
                            form=EmbeddedDocumentForm,
                            formset=EmbeddedDocumentFormSet,
                            embedded_name=None,
                            fields=None, exclude=None,
                            extra=3, can_order=False, can_delete=True,
                            max_num=None, formfield_callback=None):
    """
    Returns an ``InlineFormSet`` for the given kwargs.

    You must provide ``fk_name`` if ``model`` has more than one ``ForeignKey``
    to ``parent_model``.
    """
    emb_field = _get_embedded_field(parent_document, document, emb_name=embedded_name)
    if isinstance(emb_field, EmbeddedDocumentField):
        max_num = 1
    kwargs = {
        'form': form,
        'formfield_callback': formfield_callback,
        'formset': formset,
        'extra': extra,
        'can_delete': can_delete,
        'can_order': can_order,
        'fields': fields,
        'exclude': exclude,
        'max_num': max_num,
    }
    FormSet = documentformset_factory(document, **kwargs)
    FormSet.form._meta.embedded_field = emb_field.name
    return FormSet
