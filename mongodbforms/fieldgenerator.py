# -*- coding: utf-8 -*-

"""
Based on django mongotools (https://github.com/wpjunior/django-mongotools) by
Wilson Júnior (wilsonpjunior@gmail.com).
"""
import collections

from django import forms
from django.core.validators import EMPTY_VALUES
try:
    from django.utils.encoding import smart_text as smart_unicode
except ImportError:
    try:
        from django.utils.encoding import smart_unicode
    except ImportError:
        from django.forms.util import smart_unicode
from django.utils.text import capfirst

from mongoengine import ReferenceField as MongoReferenceField, EmbeddedDocumentField as MongoEmbeddedDocumentField, \
                ListField as MongoListField, MapField as MongoMapField

from .fields import MongoCharField, ReferenceField, DocumentMultipleChoiceField, ListField, MapField
from .widgets import DynamicListWidget
from .documentoptions import create_verbose_name

BLANK_CHOICE_DASH = [("", "---------")]

class MongoFormFieldGenerator(object):
    """This class generates Django form-fields for mongoengine-fields."""
    
    # used for fields that fit in one of the generate functions
    # but don't actually have the name.
    generator_map = {
        'sortedlistfield': 'generate_listfield',
        'longfield': 'generate_intfield',
    }
    
    form_field_map = {
        'stringfield': MongoCharField,
        'stringfield_choices': forms.TypedChoiceField,
        'stringfield_long': MongoCharField,
        'emailfield': forms.EmailField,
        'urlfield': forms.URLField,
        'intfield': forms.IntegerField,
        'intfield_choices': forms.TypedChoiceField,
        'floatfield': forms.FloatField,
        'decimalfield': forms.DecimalField,
        'booleanfield': forms.BooleanField,
        'booleanfield_choices': forms.TypedChoiceField,
        'datetimefield': forms.SplitDateTimeField,
        'referencefield': ReferenceField,
        'listfield': ListField,
        'listfield_choices': forms.MultipleChoiceField,
        'listfield_references': DocumentMultipleChoiceField,
        'mapfield': MapField,
        'filefield': forms.FileField,
        'imagefield': forms.ImageField,
    }
    
    # uses the same keys as form_field_map
    widget_override_map = {
        'stringfield_long': forms.Textarea,
    }
    
    def __init__(self, field_overrides={}, widget_overrides={}):
        self.form_field_map.update(field_overrides)
        self.widget_override_map.update(widget_overrides)

    def generate(self, field, **kwargs):
        """Tries to lookup a matching formfield generator (lowercase
        field-classname) and raises a NotImplementedError of no generator
        can be found.
        """
        # do not handle embedded documents here. They are more or less special
        # and require some form of inline formset or something more complex
        # to handle then a simple field
        if isinstance(field, MongoEmbeddedDocumentField):
            return
        
        attr_name = 'generate_%s' % field.__class__.__name__.lower()
        if hasattr(self, attr_name):
            return getattr(self, attr_name)(field, **kwargs)

        for cls in field.__class__.__bases__:
            cls_name = cls.__name__.lower()
            
            attr_name = 'generate_%s' % cls_name
            if hasattr(self, attr_name):
                return getattr(self, attr_name)(field, **kwargs)

            if cls_name in self.form_field_map:
                return getattr(self, self.generator_map.get(cls_name))(field, **kwargs)
                
        raise NotImplementedError('%s is not supported by MongoForm' % \
                            field.__class__.__name__)

    def get_field_choices(self, field, include_blank=True,
                          blank_choice=BLANK_CHOICE_DASH):
        first_choice = include_blank and blank_choice or []
        return first_choice + list(field.choices)

    def string_field(self, value):
        if value in EMPTY_VALUES:
            return None
        return smart_unicode(value)

    def integer_field(self, value):
        if value in EMPTY_VALUES:
            return None
        return int(value)

    def boolean_field(self, value):
        if value in EMPTY_VALUES:
            return None
        return value.lower() == 'true'

    def get_field_label(self, field):
        if field.verbose_name:
            return capfirst(field.verbose_name)
        if field.name is not None:
            return capfirst(create_verbose_name(field.name))
        return ''

    def get_field_help_text(self, field):
        if field.help_text:
            return field.help_text
        else:
            return ''
            
    def get_field_default(self, field):
        if isinstance(field, (MongoListField, MongoMapField)):
            f = field.field
        else:
            f = field
        d = {}
        if isinstance(f.default, collections.Callable):
            d['initial'] = field.default()
            d['show_hidden_initial'] = True
            return f.default()
        else:
            d['initial'] = field.default
        return f.default
        
    def _check_widget(self, map_key):
        if map_key in self.widget_override_map:
            return {'widget': self.widget_override_map.get(map_key)}
        else:
            return {}

    def generate_stringfield(self, field, **kwargs):
        defaults = {
            'label': self.get_field_label(field),
            'initial': self.get_field_default(field),
            'required': field.required,
            'help_text': self.get_field_help_text(field),
        }
        if field.choices:
            map_key = 'stringfield_choices'
            defaults.update({
                'choices': self.get_field_choices(field),
                'coerce': self.string_field,
            })
        elif field.max_length is None:
            map_key = 'stringfield_long'
            defaults.update({
                'min_length': field.min_length,
            })
        else:
            map_key = 'stringfield'
            defaults.update({
                'max_length': field.max_length,
                'min_length': field.min_length,
            })
            if field.regex:
                defaults['regex'] = field.regex
            
        form_class = self.form_field_map.get(map_key)
        defaults.update(self._check_widget(map_key))
        defaults.update(kwargs)
        return form_class(**defaults)

    def generate_emailfield(self, field, **kwargs):
        map_key = 'emailfield'
        defaults = {
            'required': field.required,
            'min_length': field.min_length,
            'max_length': field.max_length,
            'initial': self.get_field_default(field),
            'label': self.get_field_label(field),
            'help_text': self.get_field_help_text(field)
        }
        defaults.update(self._check_widget(map_key))
        form_class = self.form_field_map.get(map_key)
        defaults.update(kwargs)
        return form_class(**defaults)

    def generate_urlfield(self, field, **kwargs):
        map_key = 'urlfield'
        defaults = {
            'required': field.required,
            'min_length': field.min_length,
            'max_length': field.max_length,
            'initial': self.get_field_default(field),
            'label': self.get_field_label(field),
            'help_text':  self.get_field_help_text(field)
        }
        form_class = self.form_field_map.get(map_key)
        defaults.update(self._check_widget(map_key))
        defaults.update(kwargs)
        return form_class(**defaults)

    def generate_intfield(self, field, **kwargs):
        defaults = {
            'required': field.required,
            'initial': self.get_field_default(field),
            'label': self.get_field_label(field),
            'help_text': self.get_field_help_text(field)
        }
        if field.choices:
            map_key = 'intfield_choices'
            defaults.update({
                'coerce': self.integer_field,
                'empty_value': None,
                'choices': self.get_field_choices(field),
            })
        else:
            map_key = 'intfield'
            defaults.update({
                'min_value': field.min_value,
                'max_value': field.max_value,
            })
        form_class = self.form_field_map.get(map_key)
        defaults.update(self._check_widget(map_key))
        defaults.update(kwargs)
        return form_class(**defaults)

    def generate_floatfield(self, field, **kwargs):
        map_key = 'floatfield'
        defaults = {
            'label': self.get_field_label(field),
            'initial': self.get_field_default(field),
            'required': field.required,
            'min_value': field.min_value,
            'max_value': field.max_value,
            'help_text': self.get_field_help_text(field)
        }
        form_class = self.form_field_map.get(map_key)
        defaults.update(self._check_widget(map_key))
        defaults.update(kwargs)
        return form_class(**defaults)

    def generate_decimalfield(self, field, **kwargs):
        map_key = 'decimalfield'
        defaults = {
            'label': self.get_field_label(field),
            'initial': self.get_field_default(field),
            'required': field.required,
            'min_value': field.min_value,
            'max_value': field.max_value,
            'decimal_places': field.precision,
            'help_text': self.get_field_help_text(field)
        }
        form_class = self.form_field_map.get(map_key)
        defaults.update(self._check_widget(map_key))
        defaults.update(kwargs)
        return form_class(**defaults)

    def generate_booleanfield(self, field, **kwargs):
        defaults = {
            'required': field.required,
            'initial': self.get_field_default(field),
            'label': self.get_field_label(field),
            'help_text': self.get_field_help_text(field)
        }
        if field.choices:
            map_key = 'booleanfield_choices'
            defaults.update({
                'coerce': self.boolean_field,
                'empty_value': None,
                'choices': self.get_field_choices(field),
            })
        else:
            map_key = 'booleanfield'
        form_class = self.form_field_map.get(map_key)
        defaults.update(self._check_widget(map_key))
        defaults.update(kwargs)
        return form_class(**defaults)

    def generate_datetimefield(self, field, **kwargs):
        map_key = 'datetimefield'
        defaults = {
            'required': field.required,
            'initial': self.get_field_default(field),
            'label': self.get_field_label(field),
        }
        form_class = self.form_field_map.get(map_key)
        defaults.update(self._check_widget(map_key))
        defaults.update(kwargs)
        return form_class(**defaults)

    def generate_referencefield(self, field, **kwargs):
        map_key = 'referencefield'
        defaults = {
            'label': self.get_field_label(field),
            'help_text': self.get_field_help_text(field),
            'required': field.required,
            'queryset': field.document_type.objects.clone(),
        }
        form_class = self.form_field_map.get(map_key)
        defaults.update(self._check_widget(map_key))
        defaults.update(kwargs)
        return form_class(**defaults)

    def generate_listfield(self, field, **kwargs):
        # we can't really handle embedded documents here. So we just ignore them
        if isinstance(field.field, MongoEmbeddedDocumentField):
            return
        
        defaults = {
            'label': self.get_field_label(field),
            'help_text': self.get_field_help_text(field),
            'required': field.required,
        }
        if field.field.choices:
            map_key = 'listfield_choices'
            defaults.update({
                'choices': field.field.choices,
                'widget': forms.CheckboxSelectMultiple
            })
        elif isinstance(field.field, MongoReferenceField):
            map_key = 'listfield_references'
            defaults.update({
                'queryset': field.field.document_type.objects.clone(),
            })
        else:
            map_key = 'listfield'
            form_field = self.generate(field.field)
            defaults.update({
                'contained_field': form_field.__class__,
            })
        form_class = self.form_field_map.get(map_key)
        defaults.update(self._check_widget(map_key))
        defaults.update(kwargs)
        return form_class(**defaults)
        
    def generate_mapfield(self, field, **kwargs):
        # we can't really handle embedded documents here. So we just ignore them
        if isinstance(field.field, MongoEmbeddedDocumentField):
            return
            
        map_key = 'mapfield'
        form_field = self.generate(field.field)
        defaults = {
            'label': self.get_field_label(field),
            'help_text': self.get_field_help_text(field),
            'required': field.required,
            'contained_field': form_field.__class__,
        }
        form_class = self.form_field_map.get(map_key)
        defaults.update(self._check_widget(map_key))
        defaults.update(kwargs)
        return form_class(**defaults)

    def generate_filefield(self, field, **kwargs):
        map_key = 'filefield'
        defaults = {
            'required':field.required,
            'label':self.get_field_label(field),
            'initial': self.get_field_default(field),
            'help_text': self.get_field_help_text(field)
        }
        form_class = self.form_field_map.get(map_key)
        defaults.update(self._check_widget(map_key))
        defaults.update(kwargs)
        return form_class(**defaults)

    def generate_imagefield(self, field, **kwargs):
        map_key = 'imagefield'
        defaults = {
            'required':field.required,
            'label':self.get_field_label(field),
            'initial': self.get_field_default(field),
            'help_text': self.get_field_help_text(field)
        }
        form_class = self.form_field_map.get(map_key)
        defaults.update(self._check_widget(map_key))
        defaults.update(kwargs)
        return form_class(**defaults)


class MongoDefaultFormFieldGenerator(MongoFormFieldGenerator):
    """This class generates Django form-fields for mongoengine-fields."""

    def generate(self, field, **kwargs):
        """Tries to lookup a matching formfield generator (lowercase
        field-classname) and raises a NotImplementedError of no generator
        can be found.
        """
        try:
            return super(MongoDefaultFormFieldGenerator, self).generate(field, **kwargs)
        except NotImplementedError:
            # a normal charfield is always a good guess
            # for a widget.
            # TODO: Somehow add a warning
            defaults = {'required': field.required}

            if hasattr(field, 'min_length'):
                defaults['min_length'] = field.min_length

            if hasattr(field, 'max_length'):
                defaults['max_length'] = field.max_length

            if hasattr(field, 'default'):
                defaults['initial'] = field.default

            defaults.update(kwargs)
            return forms.CharField(**defaults)
            
class DynamicFormFieldGenerator(MongoDefaultFormFieldGenerator):
    widget_override_map = {
        'stringfield_long': forms.Textarea,
        'listfield': DynamicListWidget,
    }
    
