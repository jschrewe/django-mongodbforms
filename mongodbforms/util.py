from django import forms

from fields import ReferenceField

from documentoptions import AdminOptions

def init_document_options(document):
    if not hasattr(document, '_admin_opts') or not isinstance(document._admin_opts, AdminOptions):
        document._admin_opts = AdminOptions(document)
    if not isinstance(document._meta, AdminOptions):
        document._meta = document._admin_opts
    return document

def get_document_options(document):
    return AdminOptions(document)

# Taken from django-mongoforms (https://github.com/stephrdev/django-mongoforms)
# 
# Copyright (c) 2010, Stephan Jaekel <steph@rdev.info>
# All rights reserved.
class MongoFormFieldGenerator(object):
    """This class generates Django form-fields for mongoengine-fields."""
    
    def generate(self, field_name, field):
        """Tries to lookup a matching formfield generator (lowercase 
        field-classname) and raises a NotImplementedError of no generator
        can be found.
        """
        if hasattr(self, 'generate_%s' % field.__class__.__name__.lower()):
            return getattr(self, 'generate_%s' % \
                field.__class__.__name__.lower())(field_name, field)
        else:
            # a normal charfield is always a good guess
            # for a widget.
            # TODO: Somehow add a warning
            return forms.CharField(
                required=field.required,
                min_length=field.min_length,
                max_length=field.max_length,
                initial=field.default
            )
            

    def generate_stringfield(self, field_name, field):
        if field.regex:
            return forms.CharField(
                regex=field.regex,
                required=field.required,
                min_length=field.min_length,
                max_length=field.max_length,
                initial=field.default
            )
        elif field.choices:
            return forms.ChoiceField(
                required=field.required,
                initial=field.default,
                choices=zip(field.choices, field.choices)
            )
        elif field.max_length is None:
            return forms.CharField(
                required=field.required,
                initial=field.default,
                min_length=field.min_length,
                widget=forms.Textarea
            )
        else:
            return forms.CharField(
                required=field.required,
                min_length=field.min_length,
                max_length=field.max_length,
                initial=field.default
            )

    def generate_emailfield(self, field_name, field):
        return forms.EmailField(
            required=field.required,
            min_length=field.min_length,
            max_length=field.max_length,
            initial=field.default
        )

    def generate_urlfield(self, field_name, field):
        return forms.URLField(
            required=field.required,
            min_length=field.min_length,
            max_length=field.max_length,
            initial=field.default
        )

    def generate_intfield(self, field_name, field):
        return forms.IntegerField(
            required=field.required,
            min_value=field.min_value,
            max_value=field.max_value,
            initial=field.default
        )

    def generate_floatfield(self, field_name, field):
        return forms.FloatField(
            required=field.required,
            min_value=field.min_value,
            max_value=field.max_value,
            initial=field.default
        )

    def generate_decimalfield(self, field_name, field):
        return forms.DecimalField(
            required=field.required,
            min_value=field.min_value,
            max_value=field.max_value,
            initial=field.default
        )

    def generate_booleanfield(self, field_name, field):
        return forms.BooleanField(
            required=field.required,
            initial=field.default
        )

    def generate_datetimefield(self, field_name, field):
        return forms.DateTimeField(
            required=field.required,
            initial=field.default
        )

    def generate_referencefield(self, field_name, field):
        return ReferenceField(field.document_type.objects)