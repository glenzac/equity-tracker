"""
Input Validation Utilities.

Provides consistent validation across API endpoints.
"""
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal, InvalidOperation
from flask import current_app


class ValidationError(Exception):
    """Custom validation error with field information."""

    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(message)


def validate_string(value: Any, field_name: str, max_length: int = None,
                    min_length: int = 1, required: bool = True) -> Optional[str]:
    """
    Validate and sanitize a string value.

    Args:
        value: The value to validate
        field_name: Name of the field for error messages
        max_length: Maximum allowed length (defaults to config MAX_STRING_LENGTH)
        min_length: Minimum required length (default 1)
        required: Whether the field is required

    Returns:
        Sanitized string or None if not required and empty

    Raises:
        ValidationError: If validation fails
    """
    if max_length is None:
        max_length = current_app.config.get('MAX_STRING_LENGTH', 255)

    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValidationError(f"{field_name} is required", field_name)
        return None

    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string", field_name)

    value = value.strip()

    if len(value) < min_length:
        raise ValidationError(
            f"{field_name} must be at least {min_length} characters",
            field_name
        )

    if len(value) > max_length:
        raise ValidationError(
            f"{field_name} exceeds maximum length of {max_length} characters",
            field_name
        )

    return value


def validate_integer(value: Any, field_name: str, min_value: int = None,
                     max_value: int = None, required: bool = True) -> Optional[int]:
    """
    Validate an integer value.

    Args:
        value: The value to validate
        field_name: Name of the field for error messages
        min_value: Minimum allowed value
        max_value: Maximum allowed value (defaults to config MAX_QUANTITY for quantities)
        required: Whether the field is required

    Returns:
        Integer value or None if not required and empty

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        if required:
            raise ValidationError(f"{field_name} is required", field_name)
        return None

    try:
        int_value = int(value)
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name} must be a valid integer", field_name)

    if min_value is not None and int_value < min_value:
        raise ValidationError(
            f"{field_name} must be at least {min_value}",
            field_name
        )

    if max_value is not None and int_value > max_value:
        raise ValidationError(
            f"{field_name} exceeds maximum value of {max_value}",
            field_name
        )

    return int_value


def validate_positive_integer(value: Any, field_name: str,
                               max_value: int = None, required: bool = True) -> Optional[int]:
    """
    Validate a positive integer (greater than 0).

    Args:
        value: The value to validate
        field_name: Name of the field for error messages
        max_value: Maximum allowed value
        required: Whether the field is required

    Returns:
        Positive integer or None if not required

    Raises:
        ValidationError: If validation fails
    """
    if max_value is None:
        max_value = current_app.config.get('MAX_QUANTITY', 1_000_000_000)

    result = validate_integer(value, field_name, min_value=1, max_value=max_value, required=required)
    return result


def validate_decimal(value: Any, field_name: str, min_value: Decimal = None,
                     max_value: Decimal = None, required: bool = True) -> Optional[Decimal]:
    """
    Validate a decimal value.

    Args:
        value: The value to validate
        field_name: Name of the field for error messages
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        required: Whether the field is required

    Returns:
        Decimal value or None if not required

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        if required:
            raise ValidationError(f"{field_name} is required", field_name)
        return None

    try:
        dec_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(f"{field_name} must be a valid number", field_name)

    if min_value is not None and dec_value < min_value:
        raise ValidationError(
            f"{field_name} must be at least {min_value}",
            field_name
        )

    if max_value is not None and dec_value > max_value:
        raise ValidationError(
            f"{field_name} exceeds maximum value of {max_value}",
            field_name
        )

    return dec_value


def validate_positive_decimal(value: Any, field_name: str,
                               max_value: Decimal = None, required: bool = True) -> Optional[Decimal]:
    """
    Validate a positive decimal (greater than 0).

    Args:
        value: The value to validate
        field_name: Name of the field for error messages
        max_value: Maximum allowed value
        required: Whether the field is required

    Returns:
        Positive Decimal or None if not required

    Raises:
        ValidationError: If validation fails
    """
    if max_value is None:
        max_value = Decimal(str(current_app.config.get('MAX_PRICE', 10_000_000)))

    result = validate_decimal(value, field_name, min_value=Decimal('0.0001'),
                              max_value=max_value, required=required)
    return result


def validate_enum(value: Any, field_name: str, allowed_values: List[str],
                  required: bool = True, case_sensitive: bool = False) -> Optional[str]:
    """
    Validate that a value is one of the allowed values.

    Args:
        value: The value to validate
        field_name: Name of the field for error messages
        allowed_values: List of allowed values
        required: Whether the field is required
        case_sensitive: Whether comparison is case-sensitive

    Returns:
        Validated value or None if not required

    Raises:
        ValidationError: If validation fails
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValidationError(f"{field_name} is required", field_name)
        return None

    if not isinstance(value, str):
        value = str(value)

    value = value.strip()

    if case_sensitive:
        if value not in allowed_values:
            raise ValidationError(
                f"{field_name} must be one of: {', '.join(allowed_values)}",
                field_name
            )
    else:
        value_lower = value.lower()
        allowed_lower = {v.lower(): v for v in allowed_values}
        if value_lower not in allowed_lower:
            raise ValidationError(
                f"{field_name} must be one of: {', '.join(allowed_values)}",
                field_name
            )
        value = allowed_lower[value_lower]

    return value
