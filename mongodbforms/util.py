from types import MethodType

from .documentoptions import DocumentMetaWrapper

def patch_document(function, instance):
    setattr(instance, function.__name__, MethodType(function, instance))

def init_document_options(document):
    if not hasattr(document, '_meta') or not isinstance(document._meta, DocumentMetaWrapper):
        document._admin_opts = DocumentMetaWrapper(document)
    if not isinstance(document._admin_opts, DocumentMetaWrapper):
        document._admin_opts = document._meta
    return document

def get_document_options(document):
    return DocumentMetaWrapper(document)
