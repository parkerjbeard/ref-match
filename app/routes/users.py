from flask import Blueprint, request, jsonify
from app.services.user_service import UserService
from app.services.quiz_service import QuizService
from app.middleware.auth import require_auth
from app.utils.validators import validate_location
from app.utils.logger import get_logger

bp = Blueprint('users', __name__)
logger = get_logger(__name__)
user_service = UserService()
quiz_service = QuizService()


@bp.route('/profile', methods=['GET'])
@require_auth
def get_profile(current_user):
    """Get current user profile"""
    try:
        profile = user_service.get_user_profile(current_user['user_id'])
        if profile.get('error'):
            return jsonify({'error': profile['error']}), 404
        
        return jsonify(profile), 200
        
    except Exception as e:
        logger.error(f"Error getting profile: {str(e)}")
        return jsonify({'error': 'Failed to get profile'}), 500


@bp.route('/profile', methods=['PUT'])
@require_auth
def update_profile(current_user):
    """Update user profile"""
    try:
        data = request.get_json()
        
        # Validate location if provided
        if any(key in data for key in ['address', 'city', 'state', 'zip_code']):
            # Get current user data for missing fields
            profile = user_service.get_user_profile(current_user['user_id'])
            location_data = {
                'address': data.get('address', profile.get('address')),
                'city': data.get('city', profile.get('city')),
                'state': data.get('state', profile.get('state')),
                'zip_code': data.get('zip_code', profile.get('zip_code'))
            }
            
            valid, error = validate_location(**location_data)
            if not valid:
                return jsonify({'error': error}), 400
        
        result = user_service.update_profile(current_user['user_id'], data)
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify({'message': 'Profile updated successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        return jsonify({'error': 'Failed to update profile'}), 500


@bp.route('/availability', methods=['GET'])
@require_auth
def get_availability(current_user):
    """Get referee availability"""
    try:
        if current_user['role'] != 'referee':
            return jsonify({'error': 'Only referees can access availability'}), 403
        
        availability = user_service.get_availability(current_user['user_id'])
        return jsonify(availability), 200
        
    except Exception as e:
        logger.error(f"Error getting availability: {str(e)}")
        return jsonify({'error': 'Failed to get availability'}), 500


@bp.route('/availability', methods=['POST'])
@require_auth
def update_availability(current_user):
    """Update referee availability"""
    try:
        if current_user['role'] != 'referee':
            return jsonify({'error': 'Only referees can update availability'}), 403
        
        data = request.get_json()
        
        # Validate time slots format
        if 'time_slots' not in data:
            return jsonify({'error': 'time_slots required'}), 400
        
        result = user_service.update_availability(current_user['user_id'], data)
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify({'message': 'Availability updated successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error updating availability: {str(e)}")
        return jsonify({'error': 'Failed to update availability'}), 500


@bp.route('/certifications', methods=['GET'])
@require_auth
def get_certifications(current_user):
    """Get referee certifications"""
    try:
        if current_user['role'] != 'referee':
            return jsonify({'error': 'Only referees have certifications'}), 403
        
        certifications = user_service.get_certifications(current_user['user_id'])
        return jsonify(certifications), 200
        
    except Exception as e:
        logger.error(f"Error getting certifications: {str(e)}")
        return jsonify({'error': 'Failed to get certifications'}), 500


@bp.route('/quiz/<sport>/<level>', methods=['POST'])
@require_auth
def start_quiz(sport, level, current_user):
    """Start a certification quiz"""
    try:
        if current_user['role'] != 'referee':
            return jsonify({'error': 'Only referees can take quizzes'}), 403
        
        result = quiz_service.create_quiz(current_user['user_id'], sport, level)
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error starting quiz: {str(e)}")
        return jsonify({'error': 'Failed to start quiz'}), 500


@bp.route('/quiz/<int:quiz_id>/submit', methods=['POST'])
@require_auth
def submit_quiz(quiz_id, current_user):
    """Submit quiz answers"""
    try:
        data = request.get_json()
        
        if 'answers' not in data:
            return jsonify({'error': 'answers required'}), 400
        
        result = quiz_service.submit_quiz(quiz_id, data['answers'])
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error submitting quiz: {str(e)}")
        return jsonify({'error': 'Failed to submit quiz'}), 500


@bp.route('/quiz/<int:quiz_id>/results', methods=['GET'])
@require_auth
def get_quiz_results(quiz_id, current_user):
    """Get quiz results"""
    try:
        results = quiz_service.get_quiz_results(quiz_id)
        if results.get('error'):
            return jsonify({'error': results['error']}), 404
        
        return jsonify(results), 200
        
    except Exception as e:
        logger.error(f"Error getting quiz results: {str(e)}")
        return jsonify({'error': 'Failed to get results'}), 500


@bp.route('/emergency-pool', methods=['POST'])
@require_auth
def toggle_emergency_pool(current_user):
    """Toggle emergency pool opt-in"""
    try:
        if current_user['role'] != 'referee':
            return jsonify({'error': 'Only referees can join emergency pool'}), 403
        
        data = request.get_json()
        opt_in = data.get('opt_in', False)
        
        result = user_service.update_emergency_pool(current_user['user_id'], opt_in)
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        status = 'joined' if opt_in else 'left'
        return jsonify({'message': f'Successfully {status} emergency pool'}), 200
        
    except Exception as e:
        logger.error(f"Error updating emergency pool: {str(e)}")
        return jsonify({'error': 'Failed to update emergency pool'}), 500