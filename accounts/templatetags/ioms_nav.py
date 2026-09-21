from django import template

register = template.Library()


@register.filter
def has_nav_key(items, key):
    return any((item or {}).get('nav_key') == key for item in items or [])
