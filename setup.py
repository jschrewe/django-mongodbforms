#!/usr/bin/env python

from distutils.core import setup

setup(name='mongodbforms',
    version='0.1.3',
    description="An implementation of django forms using mongoengine.",
    author='Jan Schrewe',
    author_email='jan@schafproductions.com',
    url='http://www.schafproductions.com/projects/django-mongodb-forms/',
    packages=['mongodbforms',],
    package_data={
    },
    license='New BSD License',
    long_description=open('readme.md').read(),
)
