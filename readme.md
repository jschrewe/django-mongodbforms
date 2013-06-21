# django mongodbforms

This is an implementation of django's model forms for mongoengine documents.

## Requirements

  * Django >= 1.3
  * [mongoengine](http://mongoengine.org/) >= 0.6

## Usage

mongodbforms supports forms for normal documents and embedded documents. 

### Normal documents

To use mongodbforms with normal documents replace djangos forms with mongodbform forms.

    from mongodbforms import DocumentForm

    class BlogForm(DocumentForm)
        ...

### Embedded documents

For embedded documents use `EmbeddedDocumentForm`. The Meta-object of the form has to be provided with an embedded field name. The embedded object is appended to this. The form constructor takes a couple of additional arguments: The document the embedded document gets added to and an optional position argument.

If no position is provided the form adds a new embedded document to the list if the form is saved. To edit an embedded document stored in a list field the position argument is required. If you provide a position and no instance to the form the instance is automatically loaded using the position argument. If the embedded field is a plain embedded field the current object is overwritten.

````python
# forms.py
from mongodbforms import EmbeddedDocumentForm
    
class MessageForm(EmbeddedDocumentForm):
    class Meta:
	    document = Message
	    embedded_field_name = 'messages'
    
	    fields = ['subject', 'sender', 'message',]

# views.py
# create a new embedded object
form = MessageForm(parent_document=some_document, ...)
# edit the 4th embedded object
form = MessageForm(parent_document=some_document, position=3, ...)
```

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



