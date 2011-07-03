#!/usr/bin/env python

from distutils.core import setup

setup(name='mongoforms',
    version='0.1a',
    description="An implementation of django forms using mongoengine.",
    author='Jan Schrewe',
    author_email='jan@schafproductions.com',
    url='http://www.schafproductions.com',
    packages=['mongoforms',],
    package_data={
    },
)