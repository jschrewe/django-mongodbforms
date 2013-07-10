django mongodbforms
===================

This is an implementation of django's model forms for mongoengine
documents.

Requirements
------------

-  Django >= 1.3
-  `mongoengine <http://mongoengine.org/>`__ >= 0.6

Supported field types
---------------------

Mongodbforms supports all the fields that have a simple representation
in Django's formfields (IntField, TextField, etc). In addition it also
supports ``ListFields`` and ``MapFields``.

File fields
~~~~~~~~~~~

Mongodbforms handles file uploads just like the normal Django forms.
Uploaded files are stored in GridFS using the mongoengine fields.
Because GridFS has no directories and stores files in a flat space an
uploaded file whose name already exists gets a unique filename with the
form ``<filename>_<unique_number>.<extension>``.

Container fields
~~~~~~~~~~~~~~~~

For container fields like ``ListFields`` and ``MapFields`` a very simple
widget is used. The widget renders the container content in the
appropriate field plus one empty field. This is mainly done to not
introduce any Javascript dependencies, the backend code will happily
handle any kind of dynamic form, as long as the field ids are
continuously numbered in the POST data.

You can use any of the other supported fields inside list or map fields.
Including ``FileFields`` which aren't really supported by mongoengine
inside container fields.

Usage
-----

mongodbforms supports forms for normal documents and embedded documents.

Normal documents
~~~~~~~~~~~~~~~~

To use mongodbforms with normal documents replace djangos forms with
mongodbform forms.

.. code:: python

    from mongodbforms import DocumentForm

    class BlogForm(DocumentForm)
        ...

Embedded documents
~~~~~~~~~~~~~~~~~~

For embedded documents use ``EmbeddedDocumentForm``. The Meta-object of
the form has to be provided with an embedded field name. The embedded
object is appended to this. The form constructor takes a couple of
additional arguments: The document the embedded document gets added to
and an optional position argument.

If no position is provided the form adds a new embedded document to the
list if the form is saved. To edit an embedded document stored in a list
field the position argument is required. If you provide a position and
no instance to the form the instance is automatically loaded using the
position argument.

If the embedded field is a plain embedded field the current object is
simply overwritten.

.. code:: python

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

Documentation
-------------

In theory the documentation `Django's
modelform <https://docs.djangoproject.com/en/dev/topics/forms/modelforms/>`__
documentation should be all you need (except for one exception; read
on). If you find a discrepancy between something that mongodbforms does
and what Django's documentation says, you have most likely found a bug.
Please `report
it <https://github.com/jschrewe/django-mongodbforms/issues>`__.

Form field generation
~~~~~~~~~~~~~~~~~~~~~

Because the fields on mongoengine documents have no notion of form
fields mongodbform uses a generator class to generate the form field for
a db field, which is not explicitly set.

To use your own field generator you can either set a generator for your
whole project using ``MONGODBFORMS_FIELDGENERATOR`` in settings.py or
you can use the ``formfield_generator`` option on the form's Meta class.

The default generator is defined in ``mongodbforms/fieldgenerator.py``
and should make it easy to override form fields and widgets. If you set
a generator on the document form you can also pass two dicts
``field_overrides`` and ``widget_overrides`` to ``__init__``. For a list
of valid keys have a look at ``MongoFormFieldGenerator``.

.. code:: python

    # settings.py

    # set the fieldgeneretor for the whole application
    MONGODBFORMS_FIELDGENERATOR = 'myproject.fieldgenerator.GeneratorClass'

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

