from flask import Blueprint, jsonify

api_bp = Blueprint('api', __name__)


def success_response(data=None, message=None):
    """Standard success response format."""
    response = {'status': 'success'}
    if data is not None:
        response['data'] = data
    if message:
        response['message'] = message
    return jsonify(response)


def error_response(message, status_code=400):
    """Standard error response format."""
    return jsonify({
        'status': 'error',
        'message': message
    }), status_code


@api_bp.route('/health')
def health_check():
    """API health check endpoint."""
    return success_response(message='API is running')
