from django.core.exceptions import ValidationError


def validate_min_timer(value):
    if value < timedelta():
        raise ValidationError("Timer can't be negative.")
