import copy

from django.forms.widgets import Widget, Media
from django.utils.safestring import mark_safe
from django.core.validators import EMPTY_VALUES


class ListWidget(Widget):
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
    def __init__(self, widget_type, attrs=None):
        self.widget_type = widget_type
        self.widgets = []
        super(ListWidget, self).__init__(attrs)

    def render(self, name, value, attrs=None):
        if value is not None and not isinstance(value, (list, tuple)):
            raise TypeError("Value supplied for %s must be a list or tuple." % name)
        
        # save the name should we need it later
        self._name = name
        
        if value is not None:
            self.widgets = [self.widget_type() for v in value]
            
        if value is None or (len(value[-1:]) == 0 or value[-1:][0] != ''):
            # there should be exactly one empty widget at the end of the list 
            empty_widget = self.widget_type()
            empty_widget.is_required = False
            self.widgets.append(empty_widget) 
            
        if self.is_localized:
            for widget in self.widgets:
                widget.is_localized = self.is_localized
                
        output = []
        final_attrs = self.build_attrs(attrs)
        id_ = final_attrs.get('id', None)
        for i, widget in enumerate(self.widgets):
            try:
                widget_value = value[i]
            except (IndexError, TypeError):
                widget_value = None
            if id_:
                final_attrs = dict(final_attrs, id='%s_%s' % (id_, i))
            output.append(widget.render(name + '_%s' % i, widget_value, final_attrs))
        return mark_safe(self.format_output(output))

    def id_for_label(self, id_):
        # See the comment for RadioSelect.id_for_label()
        if id_:
            id_ += '_0'
        return id_

    def value_from_datadict(self, data, files, name):
        widget = self.widget_type()
        i = 0
        ret = []
        while (name + '_%s' % i) in data:
            value = widget.value_from_datadict(data, files, name + '_%s' % i)
            if value not in EMPTY_VALUES:
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
        obj.widgets = copy.deepcopy(self.widgets)
        obj.widget_type = copy.deepcopy(self.widget_type)
        return obj
    
class DynamicListWidget(ListWidget):
    def format_output(self, rendered_widgets):
        """
        Given a list of rendered widgets (as strings), returns a Unicode string
        representing the HTML for the whole lot.

        This hook allows you to format the HTML design of the widgets, if
        needed.
        """
        output = []
        for widget in rendered_widgets:
            output.append("<p>%s</p>" % widget)
        output.append('<script type="text/javascript">mdbf.onDomReady(mdbf.init("field-%s"))</script>' % self._name)
        return ''.join(output)
    
    def _get_media(self):
        "Media for a multiwidget is the combination of all media of the subwidgets"
        media = Media(js=('mongodbforms/dynamiclistwidget.js',))
        for w in self.widgets:
            media = media + w.media
        return media
    media = property(_get_media)
        
    