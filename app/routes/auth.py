from flask import Blueprint, request, jsonify
from datetime import timedelta
from app.services.auth_service import AuthService
from app.utils.validators import validate_email, validate_phone, validate_password
from app.utils.logger import get_logger

bp = Blueprint('auth', __name__)
logger = get_logger(__name__)
auth_service = AuthService()


@bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['email', 'phone', 'password', 'first_name', 'last_name', 'role']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Validate email
        valid, error = validate_email(data['email'])
        if not valid:
            return jsonify({'error': error}), 400
        
        # Validate phone
        valid, formatted_phone = validate_phone(data['phone'])
        if not valid:
            return jsonify({'error': formatted_phone}), 400
        data['phone'] = formatted_phone
        
        # Validate password
        valid, error = validate_password(data['password'])
        if not valid:
            return jsonify({'error': error}), 400
        
        # Validate role
        valid_roles = ['referee', 'organizer', 'coach']
        if data['role'] not in valid_roles:
            return jsonify({'error': f'Invalid role. Must be one of: {", ".join(valid_roles)}'}), 400
        
        # Additional fields for organizers
        if data['role'] == 'organizer':
            if not data.get('organization_name'):
                return jsonify({'error': 'organization_name is required for organizers'}), 400
        
        # Register user
        result = auth_service.register_user(data)
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify({
            'message': 'Registration successful. Please check your email to verify your account.',
            'user_id': result['user_id']
        }), 201
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500


@bp.route('/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Authenticate user
        result = auth_service.authenticate_user(data['email'], data['password'])
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 401
        
        return jsonify({
            'access_token': result['access_token'],
            'user': {
                'id': result['user']['id'],
                'email': result['user']['email'],
                'name': f"{result['user']['first_name']} {result['user']['last_name']}",
                'role': result['user']['role']
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500


@bp.route('/verify-email/<token>', methods=['GET'])
def verify_email(token):
    """Verify email address"""
    try:
        result = auth_service.verify_email(token)
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify({'message': 'Email verified successfully'}), 200
        
    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        return jsonify({'error': 'Verification failed'}), 500


@bp.route('/verify-phone', methods=['POST'])
def verify_phone():
    """Verify phone number with code"""
    try:
        data = request.get_json()
        
        if not data.get('phone') or not data.get('code'):
            return jsonify({'error': 'Phone and code are required'}), 400
        
        result = auth_service.verify_phone(data['phone'], data['code'])
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify({'message': 'Phone verified successfully'}), 200
        
    except Exception as e:
        logger.error(f"Phone verification error: {str(e)}")
        return jsonify({'error': 'Verification failed'}), 500


@bp.route('/send-phone-verification', methods=['POST'])
def send_phone_verification():
    """Send phone verification code"""
    try:
        data = request.get_json()
        
        if not data.get('phone'):
            return jsonify({'error': 'Phone is required'}), 400
        
        # Validate phone
        valid, formatted_phone = validate_phone(data['phone'])
        if not valid:
            return jsonify({'error': formatted_phone}), 400
        
        result = auth_service.send_phone_verification(formatted_phone)
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify({'message': 'Verification code sent'}), 200
        
    except Exception as e:
        logger.error(f"Send verification error: {str(e)}")
        return jsonify({'error': 'Failed to send verification code'}), 500


@bp.route('/refresh-token', methods=['POST'])
def refresh_token():
    """Refresh access token"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Invalid authorization header'}), 401
        
        token = auth_header.split(' ')[1]
        
        result = auth_service.refresh_token(token)
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 401
        
        return jsonify({'access_token': result['access_token']}), 200
        
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        return jsonify({'error': 'Token refresh failed'}), 500


@bp.route('/logout', methods=['POST'])
def logout():
    """Logout user (client should discard token)"""
    # In a stateless JWT system, logout is handled client-side
    # This endpoint is here for completeness
    return jsonify({'message': 'Logout successful'}), 200