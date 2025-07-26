from functools import wraps
from flask import request, jsonify
from app.utils.security import verify_token
from app.utils.logger import get_logger

logger = get_logger(__name__)


def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({'error': 'Authorization header missing'}), 401
        
        # Check format
        parts = auth_header.split()
        if len(parts) != 2 or parts[0] != 'Bearer':
            return jsonify({'error': 'Invalid authorization header format'}), 401
        
        token = parts[1]
        
        # Verify token
        payload = verify_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        # Add user info to kwargs
        return f(current_user=payload, *args, **kwargs)
    
    return decorated_function


def require_role(allowed_roles):
    """Decorator to require specific roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(current_user, *args, **kwargs):
            if current_user.get('role') not in allowed_roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            return f(current_user, *args, **kwargs)
        return decorated_function
    return decorator


def require_admin(f):
    """Decorator to require admin role"""
    return require_role(['admin'])(f)


def require_organizer(f):
    """Decorator to require organizer role"""
    return require_role(['organizer', 'admin'])(f)


def require_referee(f):
    """Decorator to require referee role"""
    return require_role(['referee', 'admin'])(f)