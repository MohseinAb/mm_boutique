import calendar
from django import template

register = template.Library()

@register.filter
def split(value, key):
    return value.split(key)

@register.filter
def month_name(month_number):
    try:
        return calendar.month_name[int(month_number)]
    except (ValueError, IndexError, TypeError):
        return month_number
        
@register.filter
def get_at_index(list_data, index):
    try:
        return list_data[index]
    except (IndexError, TypeError):
        return 0