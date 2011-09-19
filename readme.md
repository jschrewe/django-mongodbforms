# django mongodbforms

This is an implementation of django's model forms for mongoengine documents.

## Requirements

 * [mongoengine](http://mongoengine.org/)

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











An implementation of django's model forms for mongoengine documents. I am aware that there is already a [similar project](https://github.com/stephrdev/django-mongoforms), but I needed support for django's `modelform_factory` and `formset_factory`. The code used in this project is mostly taken from django's modelform code.

## Note

**This is pre-alpha software.** Most things are not really tested and although we try to use it wherever posible, you may stumble over weird bugs or your server might explode.

## What works

You should be able to use *mongodbforms* just like django's standard forms. If you can't you have most likely found a bug. [Report it, please.](https://github.com/jschrewe/django-mongodbforms/issues) Thank you.

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


