# -*- coding: utf-8 -*-

"""
Based on django mongotools (https://github.com/wpjunior/django-mongotools) by
Wilson Júnior (wilsonpjunior@gmail.com).
"""

from django import forms
from django.core.validators import EMPTY_VALUES

try:
    from django.utils.encoding import force_text as force_unicode
except ImportError:
    from django.utils.encoding import force_unicode
    
try:
    from django.utils.encoding import smart_text as smart_unicode
except ImportError:
    try:
        from django.utils.encoding import smart_unicode
    except ImportError:
        from django.forms.util import smart_unicode
        
from django.utils.translation import ugettext_lazy as _
from django.forms.util import ErrorList
from django.core.exceptions import ValidationError

try:  # objectid was moved into bson in pymongo 1.9
    from bson.objectid import ObjectId
    from bson.errors import InvalidId
except ImportError:
    from pymongo.objectid import ObjectId
    from pymongo.errors import InvalidId
    
from .widgets import MultiWidget

class MongoChoiceIterator(object):
    def __init__(self, field):
        self.field = field
        self.queryset = field.queryset

    def __iter__(self):
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label)

        for obj in self.queryset.all():
            yield self.choice(obj)

    def __len__(self):
        return len(self.queryset)

    def choice(self, obj):
        return (self.field.prepare_value(obj), self.field.label_from_instance(obj))

class MongoCharField(forms.CharField):
    def to_python(self, value):
        if value in EMPTY_VALUES:
            return None
        return smart_unicode(value)

class ReferenceField(forms.ChoiceField):
    """
    Reference field for mongo forms. Inspired by `django.forms.models.ModelChoiceField`.
    """
    def __init__(self, queryset, empty_label="---------",
                 *aargs, **kwaargs):

        forms.Field.__init__(self, *aargs, **kwaargs)
        self.queryset = queryset
        self.empty_label = empty_label

    def _get_queryset(self):
        return self._queryset
    
    def _set_queryset(self, queryset):
        self._queryset = queryset
        self.widget.choices = self.choices

    queryset = property(_get_queryset, _set_queryset)

    def prepare_value(self, value):
        if hasattr(value, '_meta'):
            return value.pk

        return super(ReferenceField, self).prepare_value(value)

    def _get_choices(self):
        return MongoChoiceIterator(self)

    choices = property(_get_choices, forms.ChoiceField._set_choices)

    def label_from_instance(self, obj):
        """
        This method is used to convert objects into strings; it's used to
        generate the labels for the choices presented by this object. Subclasses
        can override this method to customize the display of the choices.
        """
        return smart_unicode(obj)

    def clean(self, value):
        # Check for empty values. 
        if value in EMPTY_VALUES:
            # Raise exception if it's empty and required.
            if self.required:
                raise forms.ValidationError(self.error_messages['required'])
            # If it's not required just ignore it.
            else:
                return None

        try:
            oid = ObjectId(value)
            oid = super(ReferenceField, self).clean(oid)

            queryset = self.queryset.clone()
            obj = queryset.get(id=oid)
        except (TypeError, InvalidId, self.queryset._document.DoesNotExist):
            raise forms.ValidationError(self.error_messages['invalid_choice'] % {'value':value})
        return obj
    
    # Fix for Django 1.4
    # TODO: Test with older django versions
    # from django-mongotools by wpjunior
    # https://github.com/wpjunior/django-mongotools/
    def __deepcopy__(self, memo):
        result = super(forms.ChoiceField, self).__deepcopy__(memo)
        result.queryset = result.queryset
        result.empty_label = result.empty_label
        return result

class DocumentMultipleChoiceField(ReferenceField):
    """A MultipleChoiceField whose choices are a model QuerySet."""
    widget = forms.SelectMultiple
    hidden_widget = forms.MultipleHiddenInput
    default_error_messages = {
        'list': _('Enter a list of values.'),
        'invalid_choice': _('Select a valid choice. %s is not one of the'
                            ' available choices.'),
        'invalid_pk_value': _('"%s" is not a valid value for a primary key.')
    }

    def __init__(self, queryset, *args, **kwargs):
        super(DocumentMultipleChoiceField, self).__init__(queryset, empty_label=None, *args, **kwargs)

    def clean(self, value):
        if self.required and not value:
            raise forms.ValidationError(self.error_messages['required'])
        elif not self.required and not value:
            return []
        if not isinstance(value, (list, tuple)):
            raise forms.ValidationError(self.error_messages['list'])
        key = 'pk'

        filter_ids = []
        for pk in value:
            try:
                oid = ObjectId(pk)
                filter_ids.append(oid)
            except InvalidId:
                raise forms.ValidationError(self.error_messages['invalid_pk_value'] % pk)
        qs = self.queryset.clone()
        qs = qs.filter(**{'%s__in' % key: filter_ids})
        pks = set([force_unicode(getattr(o, key)) for o in qs])
        for val in value:
            if force_unicode(val) not in pks:
                raise forms.ValidationError(self.error_messages['invalid_choice'] % val)
        # Since this overrides the inherited ModelChoiceField.clean
        # we run custom validators here
        self.run_validators(value)
        return list(qs)

    def prepare_value(self, value):
        if hasattr(value, '__iter__') and not hasattr(value, '_meta'):
            return [super(DocumentMultipleChoiceField, self).prepare_value(v) for v in value]
        return super(DocumentMultipleChoiceField, self).prepare_value(value)
    
    
class ListField(forms.Field):
    """
    A Field that aggregates the logic of multiple Fields.

    Its clean() method takes a "decompressed" list of values, which are then
    cleaned into a single value according to self.fields. Each value in
    this list is cleaned by the corresponding field -- the first value is
    cleaned by the first field, the second value is cleaned by the second
    field, etc. Once all fields are cleaned, the list of clean values is
    "compressed" into a single value.

    Subclasses should not have to implement clean(). Instead, they must
    implement compress(), which takes a list of valid values and returns a
    "compressed" version of those values -- a single value.

    You'll probably want to use this with MultiWidget.
    """
    default_error_messages = {
        'invalid': _('Enter a list of values.'),
    }
    widget = MultiWidget

    def __init__(self, field_type, *args, **kwargs):
        self.field_type = field_type
        self.fields = []
        widget = self.field_type().widget
        if isinstance(widget, type):
            w_type = widget
        else:
            w_type = widget.__class__
        self.widget = self.widget(w_type)
        
        super(ListField, self).__init__(*args, **kwargs)
        
        if not hasattr(self, 'empty_values'):
            self.empty_values = list(EMPTY_VALUES)
        
    def _init_fields(self, initial):
        empty_val = ['',]
        if initial is None:
            initial = empty_val
        else:
            initial = initial + empty_val
            
        fields = [self.field_type(initial=d) for d in initial]
        
        return fields

    def validate(self, value):
        pass

    def clean(self, value):
        """
        Validates every value in the given list. A value is validated against
        the corresponding Field in self.fields.

        For example, if this MultiValueField was instantiated with
        fields=(DateField(), TimeField()), clean() would call
        DateField.clean(value[0]) and TimeField.clean(value[1]).
        """
        clean_data = []
        errors = ErrorList()
        if not value or isinstance(value, (list, tuple)):
            if not value or not [v for v in value if v not in self.empty_values]:
                if self.required:
                    raise ValidationError(self.error_messages['required'])
                else:
                    return []
        else:
            raise ValidationError(self.error_messages['invalid'])
        
        field = self.field_type(required=self.required)
        for field_value in value:
            if self.required and field_value in self.empty_values:
                raise ValidationError(self.error_messages['required'])
            try:
                clean_data.append(field.clean(field_value))
            except ValidationError as e:
                # Collect all validation errors in a single list, which we'll
                # raise at the end of clean(), rather than raising a single
                # exception for the first error we encounter.
                errors.extend(e.messages)
            if field.required:
                field.required = False
        if errors:
            raise ValidationError(errors)

        self.validate(clean_data)
        self.run_validators(clean_data)
        return clean_data

    def _has_changed(self, initial, data):
        if initial is None:
            initial = ['' for x in range(0, len(data))]
        for field, initial, data in zip(self.fields, initial, data):
            if field._has_changed(initial, data):
                return True
        return False

