from django.utils.datastructures import SortedDict

from django.forms.forms import BaseForm, get_declared_fields, NON_FIELD_ERRORS
from django.forms.widgets import media_property
from django.core.exceptions import FieldError, ValidationError
from django.core.validators import EMPTY_VALUES
from django.forms.util import ErrorList
from django.forms.formsets import BaseFormSet, formset_factory
from django.utils.translation import ugettext_lazy as _, ugettext
from django.utils.text import get_text_list, capfirst
from django.forms.widgets import HiddenInput

from util import MongoFormFieldGenerator
from mongoengine.fields import ObjectIdField, ListField, ReferenceField

from documentoptions import AdminOptions
from util import init_document_options


def construct_instance(form, instance, fields=None, exclude=None):
    """
    Constructs and returns a document instance from the bound ``form``'s
    ``cleaned_data``, but does not save the returned instance to the
    database.
    """
    from mongoengine.fields import FileField
    cleaned_data = form.cleaned_data
    file_field_list = []
    # check wether object is instantiated
    # TODO: IS there a better way to do this?
    if isinstance(instance, type):
        instance = instance()
        
    for f in instance._fields.itervalues():
        if isinstance(f, ObjectIdField):
            continue
        if not f.name in cleaned_data:
            continue
        if fields is not None and f.name not in fields:
            continue
        if exclude and f.name in exclude:
            continue
        # Defer saving file-type fields until after the other fields, so a
        # callable upload_to can use the values from other fields.
        if isinstance(f, FileField):
            file_field_list.append(f)
        else:
            setattr(instance, f.name, cleaned_data[f.name])

    for f in file_field_list:
        f.save_form_data(instance, cleaned_data[f.name])

    return instance


def save_instance(form, instance, fields=None, fail_message='saved',
                  commit=True, exclude=None, construct=True):
    """
    Saves bound Form ``form``'s cleaned_data into document instance ``instance``.

    If commit=True, then the changes to ``instance`` will be saved to the
    database. Returns ``instance``.

    If construct=False, assume ``instance`` has already been constructed and
    just needs to be saved.
    """
    instance = construct_instance(form, instance, fields, exclude)
    if form.errors:
        raise ValueError("The %s could not be %s because the data didn't"
                         " validate." % (instance.__class__.__name__, fail_message))

    if commit and hasattr(instance, 'save'):
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
    for f in instance._fields.itervalues():
        if fields and not f.name in fields:
            continue
        if exclude and f.name in exclude:
            continue
        else:
            data[f.name] = getattr(instance, f.name)
    return data

def fields_for_document(document, fields=None, exclude=None, widgets=None, formfield_callback=None):
    """
    Returns a ``SortedDict`` containing form fields for the given model.

    ``fields`` is an optional list of field names. If provided, only the named
    fields will be included in the returned fields.

    ``exclude`` is an optional list of field names. If provided, the named
    fields will be excluded from the returned fields, even if they are listed
    in the ``fields`` argument.
    """
    field_list = []
    ignored = []
    field_generator = MongoFormFieldGenerator()
    for f in document._fields.itervalues():
        if isinstance(f, (ObjectIdField, ListField)):
            continue
        if fields is not None and not f.name in fields:
            continue
        if exclude and f.name in exclude:
            continue
        if widgets and f.name in widgets:
            kwargs = {'widget': widgets[f.name]}
        else:
            kwargs = {}

        formfield = field_generator.generate(f.name, f)
        if formfield_callback is not None and not callable(formfield_callback):
            raise TypeError('formfield_callback must be a function or callable')
        elif formfield_callback is not None:
            formfield = formfield_callback(f, **kwargs)

        if formfield:
            field_list.append((f.name, formfield))
        else:
            ignored.append(f.name)
    field_dict = SortedDict(field_list)
    if fields:
        field_dict = SortedDict(
            [(f, field_dict.get(f)) for f in fields
                if ((not exclude) or (exclude and f not in exclude)) and (f not in ignored)]
        )
    return field_dict



class ModelFormOptions(object):
    def __init__(self, options=None):
        self.document = getattr(options, 'document', None)
        self.model = self.document
        # TODO: Move AdminOptions to mongoforms
        if isinstance(self.model._meta, dict):
            self.model._admin_opts = AdminOptions(self.model)
            self.model._meta = self.model._admin_opts
        self.fields = getattr(options, 'fields', None)
        self.exclude = getattr(options, 'exclude', None)
        self.widgets = getattr(options, 'widgets', None)
        self.embedded_field = getattr(options, 'embedded_field_name', None)
        
        
class DocumentFormMetaclass(type):
    def __new__(cls, name, bases, attrs):
        formfield_callback = attrs.pop('formfield_callback', None)
        try:
            parents = [b for b in bases if issubclass(b, DocumentForm) or issubclass(b, EmbeddedDocumentForm)]
        except NameError:
            # We are defining DocumentForm itself.
            parents = None
        declared_fields = get_declared_fields(bases, attrs, False)
        new_class = super(DocumentFormMetaclass, cls).__new__(cls, name, bases, attrs)
        if not parents:
            return new_class

        if 'media' not in attrs:
            new_class.media = media_property(new_class)
            
        opts = new_class._meta = ModelFormOptions(getattr(new_class, 'Meta', None))
        if opts.document:
            # If a model is defined, extract form fields from it.
            fields = fields_for_document(opts.document, opts.fields,
                                      opts.exclude, opts.widgets, formfield_callback)
            # make sure opts.fields doesn't specify an invalid field
            none_document_fields = [k for k, v in fields.iteritems() if not v]
            missing_fields = set(none_document_fields) - \
                             set(declared_fields.keys())
            if missing_fields:
                message = 'Unknown field(s) (%s) specified for %s'
                message = message % (', '.join(missing_fields),
                                     opts.model.__name__)
                raise FieldError(message)
            # Override default model fields with any custom declared ones
            # (plus, include all the other declared fields).
            fields.update(declared_fields)
        else:
            fields = declared_fields
            
        new_class.declared_fields = declared_fields
        new_class.base_fields = fields
        return new_class
    
    
class BaseDocumentForm(BaseForm):
    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None,
                 initial=None, error_class=ErrorList, label_suffix=':',
                 empty_permitted=False, instance=None):
        
        opts = self._meta
        
        if instance is None:
            if opts.document is None:
                raise ValueError('DocumentForm has no document class specified.')
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
        super(BaseDocumentForm, self).__init__(data, files, auto_id, prefix, object_data,
                                            error_class, label_suffix, empty_permitted)

    def _update_errors(self, message_dict):
        for k, v in message_dict.items():
            if k != NON_FIELD_ERRORS:
                self._errors.setdefault(k, self.error_class()).extend(v)
                # Remove the data from the cleaned_data dict since it was invalid
                if k in self.cleaned_data:
                    del self.cleaned_data[k]
        if NON_FIELD_ERRORS in message_dict:
            messages = message_dict[NON_FIELD_ERRORS]
            self._errors.setdefault(NON_FIELD_ERRORS, self.error_class()).extend(messages)

    def _get_validation_exclusions(self):
        """
        For backwards-compatibility, several types of fields need to be
        excluded from model validation. See the following tickets for
        details: #12507, #12521, #12553
        """
        exclude = []
        # Build up a list of fields that should be excluded from model field
        # validation and unique checks.
        for f in self.instance._fields.itervalues():
            field = f.name
            # Exclude fields that aren't on the form. The developer may be
            # adding these values to the model after form validation.
            if field not in self.fields:
                exclude.append(f.name)

            # Don't perform model validation on fields that were defined
            # manually on the form and excluded via the ModelForm's Meta
            # class. See #12901.
            elif self._meta.fields and field not in self._meta.fields:
                exclude.append(f.name)
            elif self._meta.exclude and field in self._meta.exclude:
                exclude.append(f.name)

            # Exclude fields that failed form validation. There's no need for
            # the model fields to validate them as well.
            elif field in self._errors.keys():
                exclude.append(f.name)

            # Exclude empty fields that are not required by the form, if the
            # underlying model field is required. This keeps the model field
            # from raising a required error. Note: don't exclude the field from
            # validaton if the model field allows blanks. If it does, the blank
            # value may be included in a unique check, so cannot be excluded
            # from validation.
            else:
                form_field = self.fields[field]
                field_value = self.cleaned_data.get(field, None)
                if f.required and not form_field.required and field_value in EMPTY_VALUES:
                    exclude.append(f.name)
        return exclude

    def clean(self):
        self._validate_unique = True
        return self.cleaned_data

    def _post_clean(self):
        opts = self._meta
        # Update the model instance with self.cleaned_data.
        self.instance = construct_instance(self, self.instance, opts.fields, opts.exclude)

        exclude = self._get_validation_exclusions()

        # Clean the model instance's fields.
        try:
            for f in self.instance._fields.itervalues():
                if f.name not in exclude:
                    f.validate(getattr(self.instance, f.name))
        except ValidationError, e:
            self._update_errors(e.message_dict)

        # Call the model instance's clean method.
        if hasattr(self.instance, 'clean'):
            try:
                self.instance.clean()
            except ValidationError, e:
                self._update_errors({NON_FIELD_ERRORS: e.messages})

        # Validate uniqueness if needed.
        if self._validate_unique:
            self.validate_unique()

    def validate_unique(self):
        """
        Calls the instance's validate_unique() method and updates the form's
        validation errors if any were raised.
        
        FIXME: Does nothing at the moment.
        """
        return
    

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
        except KeyError:
            fail_message = 'embedded docuement saved'
        obj = save_instance(self, self.instance, self._meta.fields,
                             fail_message, commit, construct=False)

        return obj
    save.alters_data = True

class DocumentForm(BaseDocumentForm):
    __metaclass__ = DocumentFormMetaclass
    
def documentform_factory(document, form=DocumentForm, fields=None, exclude=None,
                       formfield_callback=None):
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
    class_name = document.__class__.__name__ + 'Form'

    # Class attributes for the new form class.
    form_class_attrs = {
        'Meta': Meta,
        'formfield_callback': formfield_callback
    }

    return DocumentFormMetaclass(class_name, (form,), form_class_attrs)


class EmbeddedDocumentForm(BaseDocumentForm):
    __metaclass__ = DocumentFormMetaclass
    
    def __init__(self, parent_document, *args, **kwargs):
        super(EmbeddedDocumentForm, self).__init__(*args, **kwargs)
        # FIXME: Check if parent is a real object and not a type?
        self.parent_document = parent_document
        if self._meta.embedded_field is not None and \
                not hasattr(self.parent_document, self._meta.embedded_field):
            raise FieldError("Parent document must have field %s" % self._meta.embedded_field)
        
        # always ignore kwargs instance
        self.instance = self._meta.document
        
    def save(self, commit=True):
        if self.errors:
            raise ValueError("The %s could not be saved because the data didn't"
                         " validate." % self.instance.__class__.__name__)
        
        if commit:
            print "embedded field:"
            print self._meta.embedded_field
            print getattr(self.parent_document, self._meta.embedded_field)
            l = getattr(self.parent_document, self._meta.embedded_field)
            print type(self.instance)
            print type(self)
            l.append(self.instance)
            setattr(self.parent_document, self._meta.embedded_field, l)
            print getattr(self.parent_document, self._meta.embedded_field)
            self.parent_document.save()
        
        return self.instance


class BaseDocumentFormSet(BaseFormSet):
    """
    A ``FormSet`` for editing a queryset and/or adding new objects to it.
    """
    #model = None

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None,
                 queryset=None, **kwargs):
        self.queryset = queryset
        self._queryset = queryset
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

    def _construct_form(self, i, **kwargs):
        #if self.is_bound and i < self.initial_form_count():
            # Import goes here instead of module-level because importing
            # django.db has side effects.
            #from django.db import connections
#            pk_key = "%s-%s" % (self.add_prefix(i), self.model._meta.pk.name)
#            pk = self.data[pk_key]
#            pk_field = self.model._meta.pk
#            pk = pk_field.get_db_prep_lookup('exact', pk,
#                connection=connections[self.get_queryset().db])
#            if isinstance(pk, list):
#                pk = pk[0]
#            kwargs['instance'] = self._existing_object(pk)
        #if i < self.initial_form_count() and not kwargs.get('instance'):
        #    kwargs['instance'] = self.get_queryset()[i]
        form = super(BaseDocumentFormSet, self)._construct_form(i, **kwargs)
        return form

    def get_queryset(self):
        return self._queryset

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
            if not form.has_changed() and not form in self.initial_forms:
                continue
            obj = self.save_object(form)
            if form.cleaned_data["DELETE"]:
                try:
                    obj.delete()
                except AttributeError:
                    # if it has no delete method it is an 
                    # embedded object. We just don't add to the list
                    # and it's gone. Cook huh?
                    continue
            saved.append(obj)
        return saved

    def clean(self):
        self.validate_unique()

    def validate_unique(self):
        return
#        # Collect unique_checks and date_checks to run from all the forms.
#        all_unique_checks = set()
#        all_date_checks = set()
#        for form in self.forms:
#            if not hasattr(form, 'cleaned_data'):
#                continue
#            exclude = form._get_validation_exclusions()
#            unique_checks, date_checks = form.instance._get_unique_checks(exclude=exclude)
#            all_unique_checks = all_unique_checks.union(set(unique_checks))
#            all_date_checks = all_date_checks.union(set(date_checks))
#
#        errors = []
#        # Do each of the unique checks (unique and unique_together)
#        for uclass, unique_check in all_unique_checks:
#            seen_data = set()
#            for form in self.forms:
#                # if the form doesn't have cleaned_data then we ignore it,
#                # it's already invalid
#                if not hasattr(form, "cleaned_data"):
#                    continue
#                # get data for each field of each of unique_check
#                row_data = tuple([form.cleaned_data[field] for field in unique_check if field in form.cleaned_data])
#                if row_data and not None in row_data:
#                    # if we've aready seen it then we have a uniqueness failure
#                    if row_data in seen_data:
#                        # poke error messages into the right places and mark
#                        # the form as invalid
#                        errors.append(self.get_unique_error_message(unique_check))
#                        form._errors[NON_FIELD_ERRORS] = self.error_class([self.get_form_error()])
#                        del form.cleaned_data
#                        break
#                    # mark the data as seen
#                    seen_data.add(row_data)
#        # iterate over each of the date checks now
#        for date_check in all_date_checks:
#            seen_data = set()
#            uclass, lookup, field, unique_for = date_check
#            for form in self.forms:
#                # if the form doesn't have cleaned_data then we ignore it,
#                # it's already invalid
#                if not hasattr(self, 'cleaned_data'):
#                    continue
#                # see if we have data for both fields
#                if (form.cleaned_data and form.cleaned_data[field] is not None
#                    and form.cleaned_data[unique_for] is not None):
#                    # if it's a date lookup we need to get the data for all the fields
#                    if lookup == 'date':
#                        date = form.cleaned_data[unique_for]
#                        date_data = (date.year, date.month, date.day)
#                    # otherwise it's just the attribute on the date/datetime
#                    # object
#                    else:
#                        date_data = (getattr(form.cleaned_data[unique_for], lookup),)
#                    data = (form.cleaned_data[field],) + date_data
#                    # if we've aready seen it then we have a uniqueness failure
#                    if data in seen_data:
#                        # poke error messages into the right places and mark
#                        # the form as invalid
#                        errors.append(self.get_date_error_message(date_check))
#                        form._errors[NON_FIELD_ERRORS] = self.error_class([self.get_form_error()])
#                        del form.cleaned_data
#                        break
#                    seen_data.add(data)
#        if errors:
#            raise ValidationError(errors)

    def get_unique_error_message(self, unique_check):
        if len(unique_check) == 1:
            return ugettext("Please correct the duplicate data for %(field)s.") % {
                "field": unique_check[0],
            }
        else:
            return ugettext("Please correct the duplicate data for %(field)s, "
                "which must be unique.") % {
                    "field": get_text_list(unique_check, unicode(_("and"))),
                }

    def get_date_error_message(self, date_check):
        return ugettext("Please correct the duplicate data for %(field_name)s "
            "which must be unique for the %(lookup)s in %(date_field)s.") % {
            'field_name': date_check[2],
            'date_field': date_check[3],
            'lookup': unicode(date_check[1]),
        }

    def get_form_error(self):
        return ugettext("Please correct the duplicate values below.")

    def add_fields(self, form, index):
#        """Add a hidden field for the object's primary key."""
#        from django.db.models import AutoField, OneToOneField, ForeignKey
#        self._pk_field = pk = self.model._meta.pk
#        # If a pk isn't editable, then it won't be on the form, so we need to
#        # add it here so we can tell which object is which when we get the
#        # data back. Generally, pk.editable should be false, but for some
#        # reason, auto_created pk fields and AutoField's editable attribute is
#        # True, so check for that as well.
#        def pk_is_not_editable(pk):
#            return ((not pk.editable) or (pk.auto_created or isinstance(pk, AutoField))
#                or (pk.rel and pk.rel.parent_link and pk_is_not_editable(pk.rel.to._meta.pk)))
#        if pk_is_not_editable(pk) or pk.name not in form.fields:
#            if form.is_bound:
#                pk_value = form.instance.pk
#            else:
#                try:
#                    if index is not None:
#                        pk_value = self.get_queryset()[index].pk
#                    else:
#                        pk_value = None
#                except IndexError:
#                    pk_value = None
#            if isinstance(pk, OneToOneField) or isinstance(pk, ForeignKey):
#                qs = pk.rel.to._default_manager.get_query_set()
#            else:
#                qs = self.model._default_manager.get_query_set()
#            qs = qs.using(form.instance._state.db)
#            #form.fields[self._pk_field.name] = ModelChoiceField(qs, initial=pk_value, required=False, widget=HiddenInput)
        super(BaseDocumentFormSet, self).add_fields(form, index)

def documentformset_factory(model, form=DocumentForm, formfield_callback=None,
                         formset=BaseDocumentFormSet,
                         extra=1, can_delete=False, can_order=False,
                         max_num=None, fields=None, exclude=None):
    """
    Returns a FormSet class for the given Django model class.
    """
    form = documentform_factory(model, form=form, fields=fields, exclude=exclude,
                             formfield_callback=formfield_callback)
    FormSet = formset_factory(form, formset, extra=extra, max_num=max_num,
                              can_order=can_order, can_delete=can_delete)
    FormSet.model = model
    return FormSet



class BaseInlineDocumentFormSet(BaseDocumentFormSet):
    """
    A formset for child objects related to a parent.
    
    self.instance -> the document containing the inline objects
    """
    def __init__(self, data=None, files=None, instance=None,
                 save_as_new=False, prefix=None, queryset=None):
        self.instance = instance
        self.save_as_new = save_as_new
        
        if queryset is None:
            queryset = self.document._default_manager
            
        try:
            qs = queryset.filter(**{self.fk.name: self.instance})
        except AttributeError:
            # we received a list (hopefully)
            print "FIXME: a real queryset would be nice"
            qs = queryset
        super(BaseInlineDocumentFormSet, self).__init__(data, files, prefix=prefix, queryset=qs)

    def initial_form_count(self):
        if self.save_as_new:
            return 0
        return super(BaseInlineDocumentFormSet, self).initial_form_count()


    def _construct_form(self, i, **kwargs):
        form = super(BaseInlineDocumentFormSet, self)._construct_form(i, **kwargs)
        if self.save_as_new:
            # Remove the primary key from the form's data, we are only
            # creating new instances
            form.data[form.add_prefix(self._pk_field.name)] = None

            # Remove the foreign key from the form's data
            form.data[form.add_prefix(self.fk.name)] = None

        return form

    #@classmethod
    def get_default_prefix(cls):
        return cls.model.__name__.lower()
    get_default_prefix = classmethod(get_default_prefix)
    

    def add_fields(self, form, index):
        super(BaseInlineDocumentFormSet, self).add_fields(form, index)

        # Add the generated field to form._meta.fields if it's defined to make
        # sure validation isn't skipped on that field.
        if form._meta.fields:
            if isinstance(form._meta.fields, tuple):
                form._meta.fields = list(form._meta.fields)
            form._meta.fields.append(self.fk.name)

    def get_unique_error_message(self, unique_check):
        unique_check = [field for field in unique_check if field != self.fk.name]
        return super(BaseInlineDocumentFormSet, self).get_unique_error_message(unique_check)


def inlineformset_factory(parent_document, document, form=DocumentForm,
                          formset=BaseInlineDocumentFormSet, fk_name=None,
                          fields=None, exclude=None,
                          extra=1, can_order=False, can_delete=True, max_num=None,
                          formfield_callback=None):
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

