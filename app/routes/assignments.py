from flask import Blueprint, request, jsonify
from app.services.assignment_service import AssignmentService
from app.middleware.auth import require_auth
from app.utils.logger import get_logger

bp = Blueprint('assignments', __name__)
logger = get_logger(__name__)
assignment_service = AssignmentService()


@bp.route('/process', methods=['POST'])
@require_auth
def process_assignments(current_user):
    """Manually trigger assignment processing (admin only)"""
    try:
        if current_user['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        # Process pending games
        assignment_service.process_pending_games()
        
        return jsonify({'message': 'Assignment processing triggered'}), 200
        
    except Exception as e:
        logger.error(f"Error processing assignments: {str(e)}")
        return jsonify({'error': 'Failed to process assignments'}), 500


@bp.route('/<int:assignment_id>', methods=['GET'])
@require_auth
def get_assignment(assignment_id, current_user):
    """Get assignment details"""
    try:
        from app.database import get_db
        from app.models import Assignment, Game, User
        
        with get_db() as db:
            assignment = db.query(Assignment).filter_by(id=assignment_id).first()
            
            if not assignment:
                return jsonify({'error': 'Assignment not found'}), 404
            
            # Check access
            if current_user['role'] == 'referee' and assignment.referee_id != current_user['user_id']:
                return jsonify({'error': 'Unauthorized'}), 403
            
            # Get related data
            game = db.query(Game).filter_by(id=assignment.game_id).first()
            referee = db.query(User).filter_by(id=assignment.referee_id).first()
            
            result = {
                'id': assignment.id,
                'status': assignment.status.value,
                'is_backup': assignment.is_backup,
                'match_score': assignment.match_score,
                'distance_km': assignment.distance_km,
                'payment_amount': assignment.payment_amount,
                'notified_at': assignment.notified_at.isoformat() if assignment.notified_at else None,
                'response_deadline': assignment.response_deadline.isoformat() if assignment.response_deadline else None,
                'confirmed_at': assignment.confirmed_at.isoformat() if assignment.confirmed_at else None,
                'game': {
                    'id': game.id,
                    'sport': game.sport.value,
                    'scheduled_date': game.scheduled_date.isoformat(),
                    'location': f"{game.venue_name or game.address}, {game.city}, {game.state}",
                    'teams': f"{game.home_team} vs {game.away_team}"
                },
                'referee': {
                    'id': referee.id,
                    'name': f"{referee.first_name} {referee.last_name}",
                    'reliability_score': referee.reliability_score
                }
            }
            
            return jsonify(result), 200
            
    except Exception as e:
        logger.error(f"Error getting assignment: {str(e)}")
        return jsonify({'error': 'Failed to get assignment'}), 500


@bp.route('/<int:assignment_id>/confirm', methods=['POST'])
@require_auth
def confirm_assignment(assignment_id, current_user):
    """Confirm an assignment"""
    try:
        # Verify referee owns this assignment
        from app.database import get_db
        from app.models import Assignment
        
        with get_db() as db:
            assignment = db.query(Assignment).filter_by(id=assignment_id).first()
            
            if not assignment:
                return jsonify({'error': 'Assignment not found'}), 404
            
            if assignment.referee_id != current_user['user_id']:
                return jsonify({'error': 'Unauthorized'}), 403
        
        result = assignment_service.confirm_assignment(assignment_id)
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify({'message': 'Assignment confirmed successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error confirming assignment: {str(e)}")
        return jsonify({'error': 'Failed to confirm assignment'}), 500


@bp.route('/<int:assignment_id>/reject', methods=['POST'])
@require_auth
def reject_assignment(assignment_id, current_user):
    """Reject an assignment"""
    try:
        # Verify referee owns this assignment
        from app.database import get_db
        from app.models import Assignment
        
        with get_db() as db:
            assignment = db.query(Assignment).filter_by(id=assignment_id).first()
            
            if not assignment:
                return jsonify({'error': 'Assignment not found'}), 404
            
            if assignment.referee_id != current_user['user_id']:
                return jsonify({'error': 'Unauthorized'}), 403
        
        result = assignment_service.reject_assignment(assignment_id)
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify({'message': 'Assignment rejected'}), 200
        
    except Exception as e:
        logger.error(f"Error rejecting assignment: {str(e)}")
        return jsonify({'error': 'Failed to reject assignment'}), 500


@bp.route('/<int:assignment_id>/complete', methods=['POST'])
@require_auth
def complete_assignment(assignment_id, current_user):
    """Mark assignment as completed (admin/organizer)"""
    try:
        if current_user['role'] not in ['admin', 'organizer']:
            return jsonify({'error': 'Insufficient permissions'}), 403
        
        result = assignment_service.mark_completed(assignment_id)
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify({'message': 'Assignment marked as completed'}), 200
        
    except Exception as e:
        logger.error(f"Error completing assignment: {str(e)}")
        return jsonify({'error': 'Failed to complete assignment'}), 500


@bp.route('/<int:assignment_id>/no-show', methods=['POST'])
@require_auth
def mark_no_show(assignment_id, current_user):
    """Mark assignment as no-show (admin/organizer)"""
    try:
        if current_user['role'] not in ['admin', 'organizer']:
            return jsonify({'error': 'Insufficient permissions'}), 403
        
        result = assignment_service.mark_no_show(assignment_id)
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify({'message': 'Assignment marked as no-show'}), 200
        
    except Exception as e:
        logger.error(f"Error marking no-show: {str(e)}")
        return jsonify({'error': 'Failed to mark no-show'}), 500


@bp.route('/my-assignments', methods=['GET'])
@require_auth
def get_my_assignments(current_user):
    """Get referee's assignments"""
    try:
        if current_user['role'] != 'referee':
            return jsonify({'error': 'Only referees have assignments'}), 403
        
        from app.database import get_db
        from app.models import Assignment, Game
        
        with get_db() as db:
            # Get assignments with game details
            assignments = db.query(Assignment, Game).join(Game).filter(
                Assignment.referee_id == current_user['user_id']
            ).order_by(Game.scheduled_date.desc()).all()
            
            results = []
            for assignment, game in assignments:
                results.append({
                    'id': assignment.id,
                    'status': assignment.status.value,
                    'payment_amount': assignment.payment_amount,
                    'confirmed_at': assignment.confirmed_at.isoformat() if assignment.confirmed_at else None,
                    'game': {
                        'id': game.id,
                        'sport': game.sport.value,
                        'scheduled_date': game.scheduled_date.isoformat(),
                        'location': f"{game.city}, {game.state}",
                        'teams': f"{game.home_team} vs {game.away_team}"
                    }
                })
            
            return jsonify(results), 200
            
    except Exception as e:
        logger.error(f"Error getting assignments: {str(e)}")
        return jsonify({'error': 'Failed to get assignments'}), 500