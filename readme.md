# django mongodbforms

This is an implementation of django's model forms for mongoengine documents.

## Requirements

 * [mongoengine](http://mongoengine.org/)
 * [mongotools](https://github.com/wpjunior/django-mongotools)

## Usage

mongodbforms supports forms for normal documents and embedded documents. 

### Normal documents

To use mongodbforms with normal documents replace djangos forms with mongodbform forms.

    from mongodbforms import DocumentForm

    class BlogForm(DocumentForm)
        ...

### Embedded documents

For embedded documents use `EmbeddedDocumentForm`. The Meta-object of the form has to be provided with an embedded field name. The embedded object is appended to this. The form constructor takes an additional argument: The document the embedded document gets added to.

    # forms.py
    from mongodbforms import EmbeddedDocumentForm
    
    class MessageForm(EmbeddedDocumentForm):
        class Meta:
		    document = Message
		    embedded_field_name = 'messages'
    
		    fields = ['subject', 'sender', 'message',]

    # views.py
    form = MessageForm(parent_document=some_document, ...)

## What works and doesn't work

django-mongodbforms currently only supports the most basic things and even they are not really tested.



