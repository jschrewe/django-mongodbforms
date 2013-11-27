# -*- coding: utf-8 -*-

"""
Based on django mongotools (https://github.com/wpjunior/django-mongotools) by
Wilson Júnior (wilsonpjunior@gmail.com).
"""
import copy

from django import forms
from django.core.validators import (EMPTY_VALUES, MinLengthValidator,
                                    MaxLengthValidator)

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
    from bson.errors import InvalidId
except ImportError:
    from pymongo.errors import InvalidId
    
from mongodbforms.widgets import ListWidget, MapWidget, HiddenMapWidget


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
        return (self.field.prepare_value(obj),
                self.field.label_from_instance(obj))


class NormalizeValueMixin(object):
    """
    mongoengine doesn't treat fields that return an empty string
    as empty. This mixins can be used to create fields that return
    None instead of an empty string.
    """
    def to_python(self, value):
        value = super(NormalizeValueMixin, self).to_python(value)
        if value in EMPTY_VALUES:
            return None
        return value
        
        
class MongoCharField(NormalizeValueMixin, forms.CharField):
    pass
    

class MongoEmailField(NormalizeValueMixin, forms.EmailField):
    pass
    

class MongoSlugField(NormalizeValueMixin, forms.SlugField):
    pass
    

class MongoURLField(NormalizeValueMixin, forms.URLField):
    pass
    

class ReferenceField(forms.ChoiceField):
    """
    Reference field for mongo forms. Inspired by
    `django.forms.models.ModelChoiceField`.
    """
    def __init__(self, queryset, empty_label="---------", *args, **kwargs):
        forms.Field.__init__(self, *args, **kwargs)
        self.empty_label = empty_label
        self.queryset = queryset

    def _get_queryset(self):
        return self._queryset.clone()
    
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
        generate the labels for the choices presented by this object.
        Subclasses can override this method to customize the display of
        the choices.
        """
        return smart_unicode(obj)

    def clean(self, value):
        # Check for empty values.
        if value in EMPTY_VALUES:
            if self.required:
                raise forms.ValidationError(self.error_messages['required'])
            else:
                return None

        oid = super(ReferenceField, self).clean(value)
        
        try:
            obj = self.queryset.get(pk=oid)
        except (TypeError, InvalidId, self.queryset._document.DoesNotExist):
            raise forms.ValidationError(
                self.error_messages['invalid_choice'] % {'value': value}
            )
        return obj
    
    def __deepcopy__(self, memo):
        result = super(forms.ChoiceField, self).__deepcopy__(memo)
        result.queryset = self.queryset  # self.queryset calls clone()
        result.empty_label = copy.deepcopy(self.empty_label)
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
        super(DocumentMultipleChoiceField, self).__init__(
            queryset, empty_label=None, *args, **kwargs
        )

    def clean(self, value):
        if self.required and not value:
            raise forms.ValidationError(self.error_messages['required'])
        elif not self.required and not value:
            return []
        if not isinstance(value, (list, tuple)):
            raise forms.ValidationError(self.error_messages['list'])
        
        qs = self.queryset
        try:
            qs = qs.filter(pk__in=value)
        except ValidationError:
            raise forms.ValidationError(
                self.error_messages['invalid_pk_value'] % str(value)
            )
        pks = set([force_unicode(getattr(o, 'pk')) for o in qs])
        for val in value:
            if force_unicode(val) not in pks:
                raise forms.ValidationError(
                    self.error_messages['invalid_choice'] % val
                )
        # Since this overrides the inherited ModelChoiceField.clean
        # we run custom validators here
        self.run_validators(value)
        return list(qs)

    def prepare_value(self, value):
        if hasattr(value, '__iter__') and not hasattr(value, '_meta'):
            sup = super(DocumentMultipleChoiceField, self)
            return [sup.prepare_value(v) for v in value]
        return super(DocumentMultipleChoiceField, self).prepare_value(value)
    
    
class ListField(forms.Field):
    default_error_messages = {
        'invalid': _('Enter a list of values.'),
    }
    widget = ListWidget
    hidden_widget = forms.MultipleHiddenInput

    def __init__(self, contained_field, *args, **kwargs):
        if 'widget' in kwargs:
            self.widget = kwargs.pop('widget')
        
        if isinstance(contained_field, type):
            contained_widget = contained_field().widget
        else:
            contained_widget = contained_field.widget
            
        if isinstance(contained_widget, type):
            contained_widget = contained_widget()
        self.widget = self.widget(contained_widget)
        
        super(ListField, self).__init__(*args, **kwargs)
        
        if isinstance(contained_field, type):
            self.contained_field = contained_field(required=self.required)
        else:
            self.contained_field = contained_field
        
        if not hasattr(self, 'empty_values'):
            self.empty_values = list(EMPTY_VALUES)

    def validate(self, value):
        pass

    def clean(self, value):
        clean_data = []
        errors = ErrorList()
        if not value or isinstance(value, (list, tuple)):
            if not value or not [
                    v for v in value if v not in self.empty_values
            ]:
                if self.required:
                    raise ValidationError(self.error_messages['required'])
                else:
                    return []
        else:
            raise ValidationError(self.error_messages['invalid'])
        
        for field_value in value:
            try:
                clean_data.append(self.contained_field.clean(field_value))
            except ValidationError as e:
                # Collect all validation errors in a single list, which we'll
                # raise at the end of clean(), rather than raising a single
                # exception for the first error we encounter.
                errors.extend(e.messages)
            if self.contained_field.required:
                self.contained_field.required = False
        if errors:
            raise ValidationError(errors)

        self.validate(clean_data)
        self.run_validators(clean_data)
        return clean_data

    def _has_changed(self, initial, data):
        if initial is None:
            initial = ['' for x in range(0, len(data))]
        
        for initial, data in zip(initial, data):
            if self.contained_field._has_changed(initial, data):
                return True
        return False
        
    def prepare_value(self, value):
        value = [] if value is None else value
        value = super(ListField, self).prepare_value(value)
        prep_val = []
        for v in value:
            prep_val.append(self.contained_field.prepare_value(v))
        return prep_val


class MapField(forms.Field):
    default_error_messages = {
        'invalid': _('Enter a list of values.'),
        'key_required': _('A key is required.'),
    }
    widget = MapWidget
    hidden_widget = HiddenMapWidget

    def __init__(self, contained_field, max_key_length=None,
                 min_key_length=None, key_validators=[], field_kwargs={},
                 *args, **kwargs):
        if 'widget' in kwargs:
            self.widget = kwargs.pop('widget')
        
        if isinstance(contained_field, type):
            contained_widget = contained_field().widget
        else:
            contained_widget = contained_field.widget
            
        if isinstance(contained_widget, type):
            contained_widget = contained_widget()
        self.widget = self.widget(contained_widget)
        
        super(MapField, self).__init__(*args, **kwargs)
        
        if isinstance(contained_field, type):
            field_kwargs['required'] = self.required
            self.contained_field = contained_field(**field_kwargs)
        else:
            self.contained_field = contained_field
        
        self.key_validators = key_validators
        if min_key_length is not None:
            self.key_validators.append(MinLengthValidator(int(min_key_length)))
        if max_key_length is not None:
            self.key_validators.append(MaxLengthValidator(int(max_key_length)))
        
        # type of field used to store the dicts value
        if not hasattr(self, 'empty_values'):
            self.empty_values = list(EMPTY_VALUES)

    def _validate_key(self, key):
        if key in self.empty_values and self.required:
            raise ValidationError(self.error_messages['key_required'],
                                  code='key_required')
        errors = []
        for v in self.key_validators:
            try:
                v(key)
            except ValidationError as e:
                if hasattr(e, 'code'):
                    code = 'key_%s' % e.code
                    if code in self.error_messages:
                        e.message = self.error_messages[e.code]
                errors.extend(e.error_list)
        if errors:
            raise ValidationError(errors)

    def validate(self, value):
        pass

    def clean(self, value):
        clean_data = {}
        errors = ErrorList()
        if not value or isinstance(value, dict):
            if not value or not [
                    v for v in value.values() if v not in self.empty_values
            ]:
                if self.required:
                    raise ValidationError(self.error_messages['required'])
                else:
                    return {}
        else:
            raise ValidationError(self.error_messages['invalid'])
        
        # sort out required => at least one element must be in there
        for key, val in value.items():
            # ignore empties. Can they even come up here?
            if key in self.empty_values and val in self.empty_values:
                continue
            
            try:
                val = self.contained_field.clean(val)
            except ValidationError as e:
                # Collect all validation errors in a single list, which we'll
                # raise at the end of clean(), rather than raising a single
                # exception for the first error we encounter.
                errors.extend(e.messages)
                
            try:
                self._validate_key(key)
            except ValidationError as e:
                # Collect all validation errors in a single list, which we'll
                # raise at the end of clean(), rather than raising a single
                # exception for the first error we encounter.
                errors.extend(e.messages)
            
            clean_data[key] = val
                
            if self.contained_field.required:
                self.contained_field.required = False
                
        if errors:
            raise ValidationError(errors)

        self.validate(clean_data)
        self.run_validators(clean_data)
        return clean_data

    def _has_changed(self, initial, data):
        for k, v in data.items():
            if initial is None:
                init_val = ''
            else:
                try:
                    init_val = initial[k]
                except KeyError:
                    return True
            if self.contained_field._has_changed(init_val, v):
                return True
        return False
