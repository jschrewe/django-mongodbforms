from django import forms

from mongotools.forms.fields import MongoFormFieldGenerator as MongotoolsGenerator

from documentoptions import AdminOptions

def init_document_options(document):
    if not hasattr(document, '_admin_opts') or not isinstance(document._admin_opts, AdminOptions):
        document._admin_opts = AdminOptions(document)
    if not isinstance(document._meta, AdminOptions):
        document._meta = document._admin_opts
    return document

def get_document_options(document):
    return AdminOptions(document)

