from documentoptions import DocumentMetaWrapper

def init_document_options(document):
    if not hasattr(document, '_admin_opts') or not isinstance(document._admin_opts, DocumentMetaWrapper):
        document._admin_opts = DocumentMetaWrapper(document)
    if not isinstance(document._meta, DocumentMetaWrapper):
        document._meta = document._admin_opts
    return document

def get_document_options(document):
    return DocumentMetaWrapper(document)
