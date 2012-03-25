#!/usr/bin/env python

from setuptools import setup
from subprocess import call

def convert_readme():
    try:
        call(["pandoc", "-t",  "rst", "-o",  "README.txt", "readme.md"])
    except OSError:
        pass
    return open('README.txt').read()

setup(name='mongodbforms',
    version='0.1.4',
    description="An implementation of django forms using mongoengine.",
    author='Jan Schrewe',
    author_email='jan@schafproductions.com',
    url='http://www.schafproductions.com/projects/django-mongodb-forms/',
    packages=['mongodbforms',],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Django',
    ],
    license='New BSD License',
    long_description=convert_readme(),
    include_package_data=True,
    zip_safe=False,
    install_requires=['setuptools', 'django>=1.3', 'mongoengine>=0.6',],
)
