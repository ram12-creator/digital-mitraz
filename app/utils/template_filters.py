from flask import Blueprint
from datetime import datetime

# Create a Blueprint for our filters
filters_bp = Blueprint('filters', __name__)

@filters_bp.app_template_filter('format_date')
def format_date_filter(value, fmt='%B %d, %Y'):
    """
    Formats a date object or string into a more readable format.
    Usage in template: {{ my_date_variable|format_date }}
    or: {{ my_date_variable|format_date('%Y-%m-%d') }}
    """
    if isinstance(value, str):
        # Attempt to parse common date formats if a string is passed
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value # Return original string if parsing fails
    if isinstance(value, datetime):
        return value.strftime(fmt)
    return value