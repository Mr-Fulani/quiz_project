# blog/templatetags/blog_tags.py
from django import template


register = template.Library()


@register.filter
def endswith(value, arg):
    """Проверяет, заканчивается ли строка на заданное значение."""
    if value and isinstance(value, str):
        return value.lower().endswith(arg.lower())
    return False