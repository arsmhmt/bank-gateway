from django import template

register = template.Library()


@register.filter
def dict_get(dictionary, key):
    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(key)


@register.filter
def dict_getattr(obj, attr):
    return getattr(obj, attr, None)
