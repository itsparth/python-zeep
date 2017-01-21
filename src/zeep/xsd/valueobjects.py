import copy
from collections import OrderedDict

from zeep.xsd.printer import PrettyPrinter

__all__ = ['AnyObject', 'CompoundValue']


class AnyObject(object):
    """Create an any object

    :param xsd_object: the xsd type
    :param value: The value

    """
    def __init__(self, xsd_object, value):
        self.xsd_obj = xsd_object
        self.value = value

    def __repr__(self):
        return '<%s(type=%r, value=%r)>' % (
            self.__class__.__name__, self.xsd_elm, self.value)

    def __deepcopy__(self, memo):
        return type(self)(self.xsd_elm, copy.deepcopy(self.value))

    @property
    def xsd_type(self):
        return self.xsd_obj

    @property
    def xsd_elm(self):
        return self.xsd_obj


class CompoundValue(object):

    def __init__(self, *args, **kwargs):
        values = OrderedDict()

        # Set default values
        for container_name, container in self._xsd_type.elements_nested:
            elm_values = container.default_value
            if isinstance(elm_values, dict):
                values.update(elm_values)
            else:
                values[container_name] = elm_values

        # Set attributes
        for attribute_name, attribute in self._xsd_type.attributes:
            values[attribute_name] = attribute.default_value

        # Set elements
        items = _process_signature(self._xsd_type, args, kwargs)
        for key, value in items.items():
            values[key] = value
        self.__values__ = values

    def __contains__(self, key):
        return self.__values__.__contains__(key)

    def __eq__(self, other):
        if self.__class__ != other.__class__:
            return False

        other_values = {key: other[key] for key in other}
        return other_values == self.__values__

    def __len__(self):
        return self.__values__.__len__()

    def __iter__(self):
        return self.__values__.__iter__()

    def __repr__(self):
        return PrettyPrinter().pformat(self.__values__)

    def __delitem__(self, key):
        return self.__values__.__delitem__(key)

    def __getitem__(self, key):
        return self.__values__[key]

    def __setitem__(self, key, value):
        self.__values__[key] = value

    def __setattr__(self, key, value):
        if key.startswith('__') or key in ('_xsd_type', '_xsd_elm'):
            return super(CompoundValue, self).__setattr__(key, value)
        self.__values__[key] = value

    def __getattribute__(self, key):
        if key.startswith('__') or key in ('_xsd_type', '_xsd_elm'):
            return super(CompoundValue, self).__getattribute__(key)
        try:
            return self.__values__[key]
        except KeyError:
            raise AttributeError(
                "%s instance has no attribute '%s'" % (
                    self.__class__.__name__, key))

    def __deepcopy__(self, memo):
        new = type(self)()
        new.__values__ = copy.deepcopy(self.__values__)
        for attr, value in self.__dict__.items():
            if attr != '__values__':
                setattr(new, attr, value)
        return new


def _process_signature(xsd_type, args, kwargs):
    """Return a dict with the args/kwargs mapped to the field name.

    Special handling is done for Choice elements since we need to record which
    element the user intends to use.

    :param fields: List of tuples (name, element)
    :type fields: list
    :param args: arg tuples
    :type args: tuple
    :param kwargs: kwargs
    :type kwargs: dict


    """
    result = OrderedDict()
    # Process the positional arguments. args is currently still modified
    # in-place here
    if args:
        args = list(args)
        num_args = len(args)
        index = 0

        for element_name, element in xsd_type.elements_nested:
            values, args, index = element.parse_args(args, index)
            if not values:
                break
            result.update(values)

        for attribute_name, attribute in xsd_type.attributes:
            if num_args <= index:
                break
            result[attribute_name] = args[index]
            index += 1

        if num_args > index:
            raise TypeError(
                "__init__() takes at most %s positional arguments (%s given)" % (
                    len(result), num_args))

    # Process the named arguments (sequence/group/all/choice). The
    # available_kwargs set is modified in-place.
    available_kwargs = set(kwargs.keys())
    for element_name, element in xsd_type.elements_nested:
        if element.accepts_multiple:
            values = element.parse_kwargs(kwargs, element_name, available_kwargs)
        else:
            values = element.parse_kwargs(kwargs, None, available_kwargs)

        if values is not None:
            for key, value in values.items():
                if key not in result:
                    result[key] = value

    # Process the named arguments for attributes
    if available_kwargs:
        for attribute_name, attribute in xsd_type.attributes:
            if attribute_name in available_kwargs:
                available_kwargs.remove(attribute_name)
                result[attribute_name] = kwargs[attribute_name]

    if available_kwargs:
        raise TypeError((
            "%s() got an unexpected keyword argument %r. " +
            "Signature: (%s)"
        ) % (
            xsd_type.qname or 'ComplexType',
            next(iter(available_kwargs)),
            xsd_type.signature()))

    return result
