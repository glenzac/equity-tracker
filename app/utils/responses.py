"""
Standardized API Response Helpers.

Provides consistent response format across all API endpoints.
"""
from flask import jsonify
from typing import Any, Dict, Optional


def success_response(data: Any = None, message: str = None, status_code: int = 200):
    """
    Create a standardized success response.

    Args:
        data: Response data (dict, list, or any JSON-serializable value)
        message: Optional success message
        status_code: HTTP status code (default 200)

    Returns:
        Flask Response object with JSON content
    """
    response = {
        'status': 'success'
    }

    if data is not None:
        response['data'] = data

    if message:
        response['message'] = message

    return jsonify(response), status_code


def error_response(message: str, status_code: int = 400, errors: Dict = None, field: str = None):
    """
    Create a standardized error response.

    Args:
        message: Error message
        status_code: HTTP status code (default 400)
        errors: Optional dict of field-specific errors
        field: Optional field name that caused the error

    Returns:
        Flask Response object with JSON content
    """
    response = {
        'status': 'error',
        'message': message
    }

    if errors:
        response['errors'] = errors

    if field:
        response['field'] = field

    return jsonify(response), status_code


def created_response(data: Any, message: str = None):
    """Create a 201 Created response."""
    return success_response(data, message, 201)


def not_found_response(message: str = "Resource not found"):
    """Create a 404 Not Found response."""
    return error_response(message, 404)


def validation_error_response(message: str, field: str = None):
    """Create a 400 Validation Error response."""
    return error_response(message, 400, field=field)


def server_error_response(message: str = "An internal error occurred"):
    """Create a 500 Internal Server Error response."""
    return error_response(message, 500)
