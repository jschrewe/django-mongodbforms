#!/usr/bin/env python

from distutils.core import setup

setup(name='mongodbforms',
    version='0.1c',
    description="An implementation of django forms using mongoengine.",
    author='Jan Schrewe',
    author_email='jan@schafproductions.com',
    url='http://www.schafproductions.com',
    packages=['mongodbforms',],
    package_data={
    },
)