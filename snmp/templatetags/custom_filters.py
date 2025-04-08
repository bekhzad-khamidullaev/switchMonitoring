from django import template
import re

register = template.Library()

@register.filter
def regex_search(value, arg):
    """
    Возвращает True, если значение (value) соответствует регулярному выражению (arg).
    """
    if isinstance(value, str) and isinstance(arg, str):
        return bool(re.search(arg, value))
    return False