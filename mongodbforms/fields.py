from django.forms.fields import ChoiceField, Field
from django.core.exceptions import ValidationError
from django.utils.encoding import smart_unicode

from pymongo.objectid import ObjectId
from pymongo.errors import InvalidId


# Taken from django-mongoforms (https://github.com/stephrdev/django-mongoforms)
# 
# Copyright (c) 2010, Stephan Jaekel <steph@rdev.info>
# All rights reserved.
class ReferenceField(ChoiceField):
    """
    Reference field for mongo forms. Inspired by `django.forms.models.ModelChoiceField`.
    """
    def __init__(self, queryset, *args, **kwargs):
        Field.__init__(self, *args, **kwargs)
        self.queryset = queryset

    def _get_queryset(self):
        return self._queryset

    def _set_queryset(self, queryset):
        self._queryset = queryset
        self.widget.choices = self.choices

    queryset = property(_get_queryset, _set_queryset)

    def _get_choices(self):
        if hasattr(self, '_choices'):
            return self._choices

        self._choices = [(obj.id, smart_unicode(obj)) for obj in self.queryset]
        return self._choices
    choices = property(_get_choices, ChoiceField._set_choices)

    def clean(self, value):
        try:
            oid = ObjectId(value)
            oid = super(ReferenceField, self).clean(oid)
            obj = self.queryset.get(id=oid)
        except (TypeError, InvalidId, self.queryset._document.DoesNotExist):
            raise ValidationError(self.error_messages['invalid_choice'] % {'value':value})
        return obj
    
    def prepare_value(self, data):
        try:
            return data.id
        except AttributeError:
            return None
    
