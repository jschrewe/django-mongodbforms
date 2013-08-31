import copy

from django.forms.widgets import Widget, Media, TextInput
from django.utils.safestring import mark_safe
from django.core.validators import EMPTY_VALUES
from django.forms.util import flatatt

class ListWidget(Widget):
    def __init__(self, contained_widget, attrs=None):
        self.contained_widget = contained_widget
        if isinstance(contained_widget, type):
            self.contained_widget = self.contained_widget()
        if self.is_localized:
            self.widget.is_localized = self.is_localized
        super(ListWidget, self).__init__(attrs)

    def render(self, name, value, attrs=None):
        if value is not None and not isinstance(value, (list, tuple)):
            raise TypeError("Value supplied for %s must be a list or tuple." % name) 
                
        output = []
        value = [] if value is None else value
        final_attrs = self.build_attrs(attrs)
        id_ = final_attrs.get('id', None)
        value.append('')
        for i, widget_value in enumerate(value):
            if id_:
                final_attrs = dict(final_attrs, id='%s_%s' % (id_, i))
            output.append(self.contained_widget.render(name + '_%s' % i, widget_value, final_attrs))
        return mark_safe(self.format_output(output))

    def id_for_label(self, id_):
        # See the comment for RadioSelect.id_for_label()
        if id_:
            id_ += '_0'
        return id_

    def value_from_datadict(self, data, files, name):
        widget = self.contained_widget
        i = 0
        ret = []
        while (name + '_%s' % i) in data or (name + '_%s' % i) in files:
            value = widget.value_from_datadict(data, files, name + '_%s' % i)
            # we need a different list if we handle files. Basicly Django sends
            # back the initial values if we're not dealing with files. If we store
            # files on the list, we need to add empty values to the clean data,
            # so the list positions are kept.
            if value not in EMPTY_VALUES or (value is None and len(files) > 0):
                ret.append(value)
            i = i + 1
        return ret

    def format_output(self, rendered_widgets):
        """
        Given a list of rendered widgets (as strings), returns a Unicode string
        representing the HTML for the whole lot.

        This hook allows you to format the HTML design of the widgets, if
        needed.
        """
        return ''.join(rendered_widgets)

    def _get_media(self):
        "Media for a multiwidget is the combination of all media of the subwidgets"
        media = Media()
        for w in self.widgets:
            media = media + w.media
        return media
    media = property(_get_media)

    def __deepcopy__(self, memo):
        obj = super(ListWidget, self).__deepcopy__(memo)
        obj.contained_widget = copy.deepcopy(self.contained_widget)
        #obj.widget_type = copy.deepcopy(self.widget_type)
        return obj
    
class DynamicListWidget(ListWidget):
    def __init__(self, widget_type, attrs=None):
        class_attr = {'class': 'dynamiclistwidget'}
        if attrs is None:
            attrs = class_attr
        elif 'class' in attrs:
            attrs['class'] = '%s %s' % (attrs['class'], class_attr['class'])
        else:
            attrs.update(class_attr)
        super(DynamicListWidget, self).__init__(widget_type, attrs)
    
    def format_output(self, rendered_widgets):
        """
        Given a list of rendered widgets (as strings), returns a Unicode string
        representing the HTML for the whole lot.

        This hook allows you to format the HTML design of the widgets, if
        needed.
        """
        #print(rendered_widgets)
        output = []
        for widget in rendered_widgets:
            output.append("<p>%s</p>" % widget)
        #output.append('<script type="text/javascript">mdbf.onDomReady(mdbf.init("field-%s"))</script>' % self._name)
        return ''.join(output)
    
    def _get_media(self):
        "Media for a multiwidget is the combination of all media of the subwidgets"
        media = Media(js=('mongodbforms/dynamiclistwidget.js',))
        for w in self.widgets:
            media = media + w.media
        return media
    media = property(_get_media)


class MapWidget(Widget):
    """
    A widget that is composed of multiple widgets.

    Its render() method is different than other widgets', because it has to
    figure out how to split a single value for display in multiple widgets.
    The ``value`` argument can be one of two things:

        * A list.
        * A normal value (e.g., a string) that has been "compressed" from
          a list of values.

    In the second case -- i.e., if the value is NOT a list -- render() will
    first "decompress" the value into a list before rendering it. It does so by
    calling the decompress() method, which MultiWidget subclasses must
    implement. This method takes a single "compressed" value and returns a
    list.

    When render() does its HTML rendering, each value in the list is rendered
    with the corresponding widget -- the first value is rendered in the first
    widget, the second value is rendered in the second widget, etc.

    Subclasses may implement format_output(), which takes the list of rendered
    widgets and returns a string of HTML that formats them any way you'd like.

    You'll probably want to use this class with MultiValueField.
    """
    def __init__(self, contained_widget, attrs=None):
        self.key_widget = TextInput()
        self.key_widget.is_localized = self.is_localized
        if isinstance(contained_widget, type):
            contained_widget = contained_widget()
        self.data_widget = contained_widget
        self.data_widget.is_localized = self.is_localized
        super(MapWidget, self).__init__(attrs)

    def render(self, name, value, attrs=None):
        if value is not None and not isinstance(value, dict):
            raise TypeError("Value supplied for %s must be a dict." % name)
                
        output = []
        final_attrs = self.build_attrs(attrs)
        id_ = final_attrs.get('id', None)
        fieldset_attr = {}
        
        value = list(value.items()) # in Python 3.X dict.items() returns dynamic *view objects*
        value.append(('', ''))
        for i, (key, widget_value) in enumerate(value):
            if id_:
                fieldset_attr = dict(final_attrs, id='fieldset_%s_%s' % (id_, i))
            group = []
            group.append(mark_safe('<fieldset %s>' % flatatt(fieldset_attr)))
            
            if id_:
                final_attrs = dict(final_attrs, id='%s_key_%s' % (id_, i))
            group.append(self.key_widget.render(name + '_key_%s' % i, key, final_attrs))
            
            if id_:
                final_attrs = dict(final_attrs, id='%s_value_%s' % (id_, i))
            group.append(self.data_widget.render(name + '_value_%s' % i, widget_value, final_attrs))
            group.append(mark_safe('</fieldset>'))
            
            output.append(mark_safe(''.join(group)))
        return mark_safe(self.format_output(output))

    def id_for_label(self, id_):
        # See the comment for RadioSelect.id_for_label()
        if id_:
            id_ += '_0'
        return id_

    def value_from_datadict(self, data, files, name):
        i = 0
        ret = {}
        while (name + '_key_%s' % i) in data:
            key = self.key_widget.value_from_datadict(data, files, name + '_key_%s' % i)
            value = self.data_widget.value_from_datadict(data, files, name + '_value_%s' % i)
            if key not in EMPTY_VALUES:
                ret.update(((key, value), ))
            i = i + 1
        return ret

    def format_output(self, rendered_widgets):
        """
        Given a list of rendered widgets (as strings), returns a Unicode string
        representing the HTML for the whole lot.

        This hook allows you to format the HTML design of the widgets, if
        needed.
        """
        return ''.join(rendered_widgets)

    def _get_media(self):
        "Media for a multiwidget is the combination of all media of the subwidgets"
        media = Media()
        for w in self.widgets:
            media = media + w.media
        return media
    media = property(_get_media)

    def __deepcopy__(self, memo):
        obj = super(MapWidget, self).__deepcopy__(memo)
        obj.key_widget = copy.deepcopy(self.key_widget)
        obj.data_widget = copy.deepcopy(self.data_widget)
        return obj


    
