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

If the form is saved the new embedded object is automatically added to the provided parent document. If the embedded field is a list field the embedded document is appended to the list, if it is a plain embedded field the current object is overwritten. Note that the parent document is not saved. 

    # forms.py
    from mongodbforms import EmbeddedDocumentForm
    
    class MessageForm(EmbeddedDocumentForm):
        class Meta:
		    document = Message
		    embedded_field_name = 'messages'
    
		    fields = ['subject', 'sender', 'message',]

    # views.py
    form = MessageForm(parent_document=some_document, ...)

## Documentation

In theory the documentation [Django's modelform](https://docs.djangoproject.com/en/dev/topics/forms/modelforms/) documentation should be all you need (except for one exception; read on). If you find a discrepancy between something that mongodbforms does and what Django's documentation says, you have most likely found a bug. Please [report it](https://github.com/jschrewe/django-mongodbforms/issues).

### Form field generation

Because the fields on mongoengine documents have no notion of form fields every mongodbform uses a generator class to generate the form field for a db field, which is not explicitly set. 

If you want to use your own generator class you can use the ``formfield_generator`` option on the form's Meta class.

	# generator.py
	from mongodbforms.fieldgenerator import MongoFormFieldGenerator
	
	class MyFieldGenerator(MongoFormFieldGenerator):
		...

	# forms.py
	from mongodbforms import DocumentForm
	
	from generator import MyFieldGenerator
	
	class MessageForm(DocumentForm):
        class Meta:
			formfield_generator = MyFieldGenerator



