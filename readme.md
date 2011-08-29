# django mongodbforms

This is an implementation of django's model forms for mongoengine documents.

## Requirements

 * mongoengine

## Usage



## What works and doesn't work

django-mongodbforms currently only supports the most basic things and even they are not really tested.

Changelists only support basic listings you probably won't be able to use fieldlists and every other feature that django supports for changelists (search, etc.).

Inline admin objects are created automatically for embedded objects, but can't be defined manually for referenced objects. Although I haven't tested it, field widget can't be overwritten.

