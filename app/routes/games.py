from flask import Blueprint, request, jsonify
from datetime import datetime
from app.services.game_service import GameService
from app.middleware.auth import require_auth, require_organizer
from app.utils.validators import validate_location
from app.utils.logger import get_logger

bp = Blueprint('games', __name__)
logger = get_logger(__name__)
game_service = GameService()


@bp.route('/', methods=['POST'])
@require_auth
@require_organizer
def create_game(current_user):
    """Create a new game"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['sport', 'certification_level_required', 'scheduled_date', 
                          'address', 'city', 'state', 'zip_code']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Validate location
        valid, error = validate_location(
            data['address'], data['city'], data['state'], data['zip_code']
        )
        if not valid:
            return jsonify({'error': error}), 400
        
        # Parse scheduled date
        try:
            scheduled_date = datetime.fromisoformat(data['scheduled_date'])
            if scheduled_date < datetime.utcnow():
                return jsonify({'error': 'Scheduled date must be in the future'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use ISO format'}), 400
        
        # Add organizer ID
        data['organizer_id'] = current_user['user_id']
        
        # Create game
        result = game_service.create_game(data)
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify({
            'message': 'Game created successfully',
            'game_id': result['game_id']
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating game: {str(e)}")
        return jsonify({'error': 'Failed to create game'}), 500


@bp.route('/', methods=['GET'])
@require_auth
def get_games(current_user):
    """Get games based on user role"""
    try:
        # Get query parameters
        status = request.args.get('status')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Parse dates if provided
        if start_date:
            try:
                start_date = datetime.fromisoformat(start_date)
            except ValueError:
                return jsonify({'error': 'Invalid start_date format'}), 400
        
        if end_date:
            try:
                end_date = datetime.fromisoformat(end_date)
            except ValueError:
                return jsonify({'error': 'Invalid end_date format'}), 400
        
        # Get games based on role
        if current_user['role'] == 'organizer':
            games = game_service.get_organizer_games(
                current_user['user_id'], status, start_date, end_date
            )
        elif current_user['role'] == 'referee':
            games = game_service.get_referee_games(
                current_user['user_id'], status, start_date, end_date
            )
        else:
            games = game_service.get_all_games(status, start_date, end_date)
        
        return jsonify(games), 200
        
    except Exception as e:
        logger.error(f"Error getting games: {str(e)}")
        return jsonify({'error': 'Failed to get games'}), 500


@bp.route('/<int:game_id>', methods=['GET'])
@require_auth
def get_game(game_id, current_user):
    """Get game details"""
    try:
        game = game_service.get_game_details(game_id)
        if game.get('error'):
            return jsonify({'error': game['error']}), 404
        
        return jsonify(game), 200
        
    except Exception as e:
        logger.error(f"Error getting game: {str(e)}")
        return jsonify({'error': 'Failed to get game'}), 500


@bp.route('/<int:game_id>', methods=['PUT'])
@require_auth
@require_organizer
def update_game(game_id, current_user):
    """Update game details"""
    try:
        data = request.get_json()
        
        # Check if user owns the game
        game = game_service.get_game_details(game_id)
        if game.get('error'):
            return jsonify({'error': 'Game not found'}), 404
        
        if game['organizer_id'] != current_user['user_id']:
            return jsonify({'error': 'Unauthorized to update this game'}), 403
        
        # Validate updates
        if 'scheduled_date' in data:
            try:
                scheduled_date = datetime.fromisoformat(data['scheduled_date'])
                if scheduled_date < datetime.utcnow():
                    return jsonify({'error': 'Scheduled date must be in the future'}), 400
            except ValueError:
                return jsonify({'error': 'Invalid date format'}), 400
        
        result = game_service.update_game(game_id, data)
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify({'message': 'Game updated successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error updating game: {str(e)}")
        return jsonify({'error': 'Failed to update game'}), 500


@bp.route('/<int:game_id>/cancel', methods=['POST'])
@require_auth
@require_organizer
def cancel_game(game_id, current_user):
    """Cancel a game"""
    try:
        # Check if user owns the game
        game = game_service.get_game_details(game_id)
        if game.get('error'):
            return jsonify({'error': 'Game not found'}), 404
        
        if game['organizer_id'] != current_user['user_id']:
            return jsonify({'error': 'Unauthorized to cancel this game'}), 403
        
        result = game_service.cancel_game(game_id)
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify({'message': 'Game cancelled successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error cancelling game: {str(e)}")
        return jsonify({'error': 'Failed to cancel game'}), 500


@bp.route('/submit-via-email', methods=['POST'])
def submit_game_via_email():
    """Submit game via email (webhook endpoint)"""
    try:
        # This would be called by an email service webhook
        # Parse email content and create game
        data = request.get_json()
        
        # Extract game details from email
        email_content = data.get('content', '')
        from_email = data.get('from', '')
        
        # Parse email content (simplified example)
        parsed_data = game_service.parse_email_submission(email_content, from_email)
        
        if parsed_data.get('error'):
            # Send error notification back
            logger.error(f"Failed to parse email submission: {parsed_data['error']}")
            return jsonify({'error': parsed_data['error']}), 400
        
        # Create game
        result = game_service.create_game(parsed_data)
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify({'message': 'Game submitted successfully', 'game_id': result['game_id']}), 201
        
    except Exception as e:
        logger.error(f"Error processing email submission: {str(e)}")
        return jsonify({'error': 'Failed to process submission'}), 500