from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from app.middleware.auth import require_auth, require_admin
from app.database import get_db
from app.models import User, Game, Assignment, Payment, Review
from app.models.game import GameStatus
from app.models.assignment import AssignmentStatus
from app.models.payment import PaymentStatus
from app.services.assignment_service import AssignmentService
from app.utils.logger import get_logger
import csv
import io

bp = Blueprint('admin', __name__)
logger = get_logger(__name__)
assignment_service = AssignmentService()


@bp.route('/dashboard', methods=['GET'])
@require_auth
@require_admin
def dashboard(current_user):
    """Get admin dashboard statistics"""
    try:
        with get_db() as db:
            # User statistics
            from app.models.user import UserRole
            total_referees = db.query(User).filter(User.role == UserRole.REFEREE).count()
            active_referees = db.query(User).filter(User.role == UserRole.REFEREE, User.is_active == True).count()
            total_organizers = db.query(User).filter(User.role == UserRole.ORGANIZER).count()
            
            # Game statistics
            total_games = db.query(Game).count()
            pending_games = db.query(Game).filter_by(status=GameStatus.PENDING).count()
            completed_games = db.query(Game).filter_by(status=GameStatus.COMPLETED).count()
            
            # Assignment statistics
            total_assignments = db.query(Assignment).count()
            successful_assignments = db.query(Assignment).filter_by(
                status=AssignmentStatus.COMPLETED
            ).count()
            no_shows = db.query(Assignment).filter_by(
                status=AssignmentStatus.NO_SHOW
            ).count()
            
            # Calculate success rate
            if total_assignments > 0:
                success_rate = (successful_assignments / total_assignments) * 100
                no_show_rate = (no_shows / total_assignments) * 100
            else:
                success_rate = 0
                no_show_rate = 0
            
            # Payment statistics
            from sqlalchemy import func
            total_revenue = db.query(Payment).filter_by(
                status=PaymentStatus.COMPLETED
            ).with_entities(func.sum(Payment.amount)).scalar() or 0
            
            # Recent activity
            recent_games = db.query(Game).order_by(
                Game.created_at.desc()
            ).limit(10).all()
            
            recent_assignments = db.query(Assignment, Game, User).join(
                Game, Assignment.game_id == Game.id
            ).join(
                User, Assignment.referee_id == User.id
            ).order_by(
                Assignment.created_at.desc()
            ).limit(10).all()
            
            return jsonify({
                'statistics': {
                    'users': {
                        'total_referees': total_referees,
                        'active_referees': active_referees,
                        'total_organizers': total_organizers
                    },
                    'games': {
                        'total': total_games,
                        'pending': pending_games,
                        'completed': completed_games
                    },
                    'assignments': {
                        'total': total_assignments,
                        'successful': successful_assignments,
                        'no_shows': no_shows,
                        'success_rate': round(success_rate, 2),
                        'no_show_rate': round(no_show_rate, 2)
                    },
                    'financials': {
                        'total_revenue': total_revenue
                    }
                },
                'recent_activity': {
                    'games': [{
                        'id': g.id,
                        'sport': g.sport.value,
                        'date': g.scheduled_date.isoformat(),
                        'status': g.status.value,
                        'created': g.created_at.isoformat()
                    } for g in recent_games],
                    'assignments': [{
                        'id': a.id,
                        'game_sport': g.sport.value,
                        'game_date': g.scheduled_date.isoformat(),
                        'referee': f"{u.first_name} {u.last_name}",
                        'status': a.status.value,
                        'created': a.created_at.isoformat()
                    } for a, g, u in recent_assignments]
                }
            }), 200
            
    except Exception as e:
        logger.error(f"Error getting dashboard: {str(e)}")
        return jsonify({'error': 'Failed to get dashboard'}), 500


@bp.route('/reports/assignments', methods=['GET'])
@require_auth
@require_admin
def assignment_report(current_user):
    """Generate assignment report"""
    try:
        # Get date range from query params
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if start_date:
            start_date = datetime.fromisoformat(start_date)
        else:
            start_date = datetime.utcnow() - timedelta(days=30)
            
        if end_date:
            end_date = datetime.fromisoformat(end_date)
        else:
            end_date = datetime.utcnow()
        
        with get_db() as db:
            # Get assignments in date range
            assignments = db.query(
                Assignment, Game, User
            ).join(
                Game, Assignment.game_id == Game.id
            ).join(
                User, Assignment.referee_id == User.id
            ).filter(
                Game.scheduled_date.between(start_date, end_date)
            ).all()
            
            # Generate report data
            report_data = []
            for assignment, game, referee in assignments:
                report_data.append({
                    'assignment_id': assignment.id,
                    'game_date': game.scheduled_date.isoformat(),
                    'sport': game.sport.value,
                    'location': f"{game.city}, {game.state}",
                    'referee_name': f"{referee.first_name} {referee.last_name}",
                    'referee_reliability': referee.reliability_score,
                    'assignment_status': assignment.status.value,
                    'match_score': assignment.match_score,
                    'distance_km': assignment.distance_km,
                    'payment_amount': assignment.payment_amount,
                    'confirmed_at': assignment.confirmed_at.isoformat() if assignment.confirmed_at else None
                })
            
            # Calculate summary statistics
            total = len(report_data)
            completed = len([a for a in report_data if a['assignment_status'] == 'completed'])
            no_shows = len([a for a in report_data if a['assignment_status'] == 'no_show'])
            
            return jsonify({
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'summary': {
                    'total_assignments': total,
                    'completed': completed,
                    'no_shows': no_shows,
                    'completion_rate': (completed / total * 100) if total > 0 else 0
                },
                'data': report_data
            }), 200
            
    except Exception as e:
        logger.error(f"Error generating assignment report: {str(e)}")
        return jsonify({'error': 'Failed to generate report'}), 500


@bp.route('/reports/referees', methods=['GET'])
@require_auth
@require_admin
def referee_performance_report(current_user):
    """Generate referee performance report"""
    try:
        with get_db() as db:
            # Get all active referees with their stats
            referees = db.query(User).filter_by(
                role='referee',
                is_active=True
            ).all()
            
            report_data = []
            for referee in referees:
                # Get completed assignments
                completed = db.query(Assignment).filter_by(
                    referee_id=referee.id,
                    status=AssignmentStatus.COMPLETED
                ).count()
                
                # Get no-shows
                no_shows = db.query(Assignment).filter_by(
                    referee_id=referee.id,
                    status=AssignmentStatus.NO_SHOW
                ).count()
                
                # Get average rating
                reviews = db.query(Review).filter(
                    Review.referee_id == referee.id,
                    Review.rating != None
                ).all()
                
                if reviews:
                    avg_rating = sum(r.rating for r in reviews) / len(reviews)
                else:
                    avg_rating = 0
                
                report_data.append({
                    'referee_id': referee.id,
                    'name': f"{referee.first_name} {referee.last_name}",
                    'email': referee.email,
                    'phone': referee.phone,
                    'reliability_score': referee.reliability_score,
                    'total_games_completed': completed,
                    'no_show_count': no_shows,
                    'average_rating': round(avg_rating, 2),
                    'total_reviews': len(reviews),
                    'emergency_pool': referee.emergency_pool_opt_in
                })
            
            # Sort by reliability score
            report_data.sort(key=lambda x: x['reliability_score'], reverse=True)
            
            return jsonify({
                'total_referees': len(report_data),
                'data': report_data
            }), 200
            
    except Exception as e:
        logger.error(f"Error generating referee report: {str(e)}")
        return jsonify({'error': 'Failed to generate report'}), 500


@bp.route('/reports/revenue', methods=['GET'])
@require_auth
@require_admin
def revenue_report(current_user):
    """Generate revenue report"""
    try:
        # Get date range
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if start_date:
            start_date = datetime.fromisoformat(start_date)
        else:
            start_date = datetime.utcnow() - timedelta(days=30)
            
        if end_date:
            end_date = datetime.fromisoformat(end_date)
        else:
            end_date = datetime.utcnow()
        
        with get_db() as db:
            # Get all completed payments in date range
            payments = db.query(Payment).filter(
                Payment.status == PaymentStatus.COMPLETED,
                Payment.created_at.between(start_date, end_date)
            ).all()
            
            # Calculate totals
            total_revenue = 0
            total_payouts = 0
            total_fees = 0
            
            for payment in payments:
                if payment.payment_type.value == 'game_payment':
                    total_revenue += payment.amount
                elif payment.payment_type.value == 'payout':
                    total_payouts += payment.amount
                    # Calculate platform fee
                    fee = payment.amount * Config.PLATFORM_FEE_PERCENTAGE / (1 - Config.PLATFORM_FEE_PERCENTAGE)
                    total_fees += fee
            
            # Group by day
            daily_revenue = {}
            for payment in payments:
                date_key = payment.created_at.date().isoformat()
                if date_key not in daily_revenue:
                    daily_revenue[date_key] = {
                        'revenue': 0,
                        'payouts': 0,
                        'fees': 0,
                        'transactions': 0
                    }
                
                if payment.payment_type.value == 'game_payment':
                    daily_revenue[date_key]['revenue'] += payment.amount
                elif payment.payment_type.value == 'payout':
                    daily_revenue[date_key]['payouts'] += payment.amount
                    fee = payment.amount * Config.PLATFORM_FEE_PERCENTAGE / (1 - Config.PLATFORM_FEE_PERCENTAGE)
                    daily_revenue[date_key]['fees'] += fee
                
                daily_revenue[date_key]['transactions'] += 1
            
            return jsonify({
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'summary': {
                    'total_revenue': round(total_revenue, 2),
                    'total_payouts': round(total_payouts, 2),
                    'total_platform_fees': round(total_fees, 2),
                    'net_revenue': round(total_fees, 2)
                },
                'daily_breakdown': daily_revenue
            }), 200
            
    except Exception as e:
        logger.error(f"Error generating revenue report: {str(e)}")
        return jsonify({'error': 'Failed to generate report'}), 500


@bp.route('/manual-assignment', methods=['POST'])
@require_auth
@require_admin
def manual_assignment(current_user):
    """Manually assign referee to game"""
    try:
        data = request.get_json()
        
        if not data.get('game_id') or not data.get('referee_id'):
            return jsonify({'error': 'game_id and referee_id required'}), 400
        
        with get_db() as db:
            # Check game exists and is pending
            game = db.query(Game).filter_by(id=data['game_id']).first()
            if not game:
                return jsonify({'error': 'Game not found'}), 404
            
            if game.status != GameStatus.PENDING:
                return jsonify({'error': 'Game is not pending assignment'}), 400
            
            # Check referee exists
            referee = db.query(User).filter_by(
                id=data['referee_id'],
                role='referee'
            ).first()
            
            if not referee:
                return jsonify({'error': 'Referee not found'}), 404
            
            # Create assignment
            from app.models import Assignment
            from app.models.assignment import AssignmentStatus
            
            assignment = Assignment(
                game_id=game.id,
                referee_id=referee.id,
                status=AssignmentStatus.CONFIRMED,
                match_score=1.0,  # Manual assignment gets max score
                payment_amount=game.final_rate,
                confirmed_at=datetime.utcnow()
            )
            
            db.add(assignment)
            game.status = GameStatus.ASSIGNED
            db.commit()
            
            # Send notification
            from app.services.notification_service import NotificationService
            notification_service = NotificationService()
            notification_service.send_confirmation_notification(assignment)
            
            logger.info(f"Manual assignment created: Game {game.id} to Referee {referee.id}")
            
            return jsonify({
                'message': 'Assignment created successfully',
                'assignment_id': assignment.id
            }), 201
            
    except Exception as e:
        logger.error(f"Error creating manual assignment: {str(e)}")
        return jsonify({'error': 'Failed to create assignment'}), 500


@bp.route('/export/<report_type>', methods=['GET'])
@require_auth
@require_admin
def export_report(report_type, current_user):
    """Export report as CSV"""
    try:
        # Generate report based on type
        if report_type == 'referees':
            response = referee_performance_report(current_user)
            data = response[0].get_json()['data']
            
            # Create CSV
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=[
                'referee_id', 'name', 'email', 'phone', 'reliability_score',
                'total_games_completed', 'no_show_count', 'average_rating',
                'total_reviews', 'emergency_pool'
            ])
            writer.writeheader()
            writer.writerows(data)
            
            # Return CSV file
            from flask import Response
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={
                    'Content-Disposition': f'attachment; filename=referee_report_{datetime.utcnow().date()}.csv'
                }
            )
            
        else:
            return jsonify({'error': 'Invalid report type'}), 400
            
    except Exception as e:
        logger.error(f"Error exporting report: {str(e)}")
        return jsonify({'error': 'Failed to export report'}), 500