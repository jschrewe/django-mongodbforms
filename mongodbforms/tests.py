# -*- coding: utf-8 -*-
from django.conf import settings

settings.configure(
    DEBUG=True,
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
        }
    },
    ROOT_URLCONF='',
    INSTALLED_APPS=(
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.admin',
        'mongodbforms',
    )
)


import mongoengine
from django.test import SimpleTestCase
from mongodbforms.documentoptions import LazyDocumentMetaWrapper


class TestDocument(mongoengine.Document):
    meta = {'abstract': True}

    name = mongoengine.StringField()


class LazyWrapperTest(SimpleTestCase):

    def test_lazy_getitem(self):
        meta = LazyDocumentMetaWrapper(TestDocument)
        self.assertTrue(meta['abstract'])

        meta = LazyDocumentMetaWrapper(TestDocument)
        self.assertTrue(meta.get('abstract'))

        meta = LazyDocumentMetaWrapper(TestDocument)
        self.assertTrue('abstract' in meta)

        meta = LazyDocumentMetaWrapper(TestDocument)
        self.assertEqual(len(meta), 1)

        meta = LazyDocumentMetaWrapper(TestDocument)
        meta.custom = 'yes'
        self.assertEqual(meta.custom, 'yes')
