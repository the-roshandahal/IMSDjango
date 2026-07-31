from django import template

register = template.Library()


@register.filter
def dict_get(mapping, key):
    if mapping is None:
        return None
    return mapping.get(key)
