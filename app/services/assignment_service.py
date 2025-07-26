from datetime import datetime, timedelta
from typing import Dict, List, Optional
from app.database import DatabaseManager, get_db
from app.models import Assignment, Game, User
from app.models.assignment import AssignmentStatus
from app.models.game import GameStatus
from app.services.matching_service import MatchingService
from app.services.notification_service import NotificationService
from app.integrations import TwilioClient, SendGridClient
from config.config import Config
from app.utils.logger import get_logger
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

logger = get_logger(__name__)


class AssignmentService:
    """Service for managing game assignments"""
    
    def __init__(self):
        self.assignment_db = DatabaseManager(Assignment)
        self.game_db = DatabaseManager(Game)
        self.matching_service = MatchingService()
        self.notification_service = NotificationService()
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        atexit.register(lambda: self.scheduler.shutdown())
    
    def process_pending_games(self):
        """Process all pending games and create assignments"""
        try:
            logger.info("Starting assignment processing for pending games")
            
            with get_db() as db:
                # Get pending games
                pending_games = db.query(Game).filter(
                    Game.status == GameStatus.PENDING,
                    Game.scheduled_date > datetime.utcnow()
                ).all()
                
                logger.info(f"Found {len(pending_games)} pending games")
                
                for game in pending_games:
                    # Check if already has assignment
                    existing = db.query(Assignment).filter(
                        Assignment.game_id == game.id,
                        Assignment.status.in_([
                            AssignmentStatus.NOTIFIED,
                            AssignmentStatus.CONFIRMED
                        ])
                    ).first()
                    
                    if existing:
                        continue
                    
                    # Find best referee
                    match_result = self.matching_service.find_best_referee(game)
                    
                    if match_result:
                        referee, score = match_result
                        
                        # Create assignment
                        assignment = self._create_assignment(game, referee, score, is_backup=False)
                        
                        # Send notification
                        self.notification_service.send_assignment_notification(assignment)
                        
                        # Schedule confirmation deadline
                        self._schedule_confirmation_deadline(assignment)
                        
                        # Find and create backup assignments
                        backups = self.matching_service.find_backup_referees(game, referee.id)
                        for backup_ref, backup_score in backups:
                            self._create_assignment(game, backup_ref, backup_score, is_backup=True)
                        
                        # Update game status
                        game.status = GameStatus.ASSIGNED
                        db.commit()
                        
                    else:
                        # No referee found, check emergency pool
                        emergency_match = self.matching_service.check_emergency_pool(game)
                        
                        if emergency_match:
                            referee, score = emergency_match
                            
                            # Apply surge pricing for emergency assignment
                            game.surge_multiplier = min(game.surge_multiplier * 1.2, Config.SURGE_PRICING_CAP)
                            game.final_rate = game.base_rate * game.surge_multiplier
                            
                            # Create emergency assignment
                            assignment = self._create_assignment(game, referee, score, is_backup=False)
                            
                            # Send notification with surge pricing
                            self.notification_service.send_assignment_notification(assignment, is_emergency=True)
                            
                            # Schedule confirmation deadline
                            self._schedule_confirmation_deadline(assignment)
                            
                            game.status = GameStatus.ASSIGNED
                            db.commit()
                        else:
                            logger.warning(f"No referee found for game {game.id}")
                            # Could notify organizer here
                
        except Exception as e:
            logger.error(f"Error processing pending games: {str(e)}")
    
    def confirm_assignment(self, assignment_id: int) -> Dict:
        """Confirm an assignment"""
        try:
            with get_db() as db:
                assignment = db.query(Assignment).filter_by(id=assignment_id).first()
                
                if not assignment:
                    return {'error': 'Assignment not found'}
                
                if assignment.status != AssignmentStatus.NOTIFIED:
                    return {'error': 'Assignment cannot be confirmed in current status'}
                
                # Check if within deadline
                if datetime.utcnow() > assignment.response_deadline:
                    return {'error': 'Confirmation deadline has passed'}
                
                # Update assignment
                assignment.status = AssignmentStatus.CONFIRMED
                assignment.confirmed_at = datetime.utcnow()
                
                # Update referee reliability
                self.matching_service.update_referee_reliability(
                    assignment.referee_id, 'confirmed'
                )
                
                # Cancel backup assignments
                backups = db.query(Assignment).filter(
                    Assignment.game_id == assignment.game_id,
                    Assignment.is_backup == True,
                    Assignment.status == AssignmentStatus.PENDING
                ).all()
                
                for backup in backups:
                    backup.status = AssignmentStatus.CANCELLED
                
                db.commit()
                
                # Send confirmation notification
                self.notification_service.send_confirmation_notification(assignment)
                
                # Schedule game day reminder
                self._schedule_game_day_reminder(assignment)
                
                logger.info(f"Assignment {assignment_id} confirmed")
                return {'success': True}
                
        except Exception as e:
            logger.error(f"Error confirming assignment: {str(e)}")
            return {'error': 'Failed to confirm assignment'}
    
    def reject_assignment(self, assignment_id: int) -> Dict:
        """Reject an assignment"""
        try:
            with get_db() as db:
                assignment = db.query(Assignment).filter_by(id=assignment_id).first()
                
                if not assignment:
                    return {'error': 'Assignment not found'}
                
                if assignment.status != AssignmentStatus.NOTIFIED:
                    return {'error': 'Assignment cannot be rejected in current status'}
                
                # Update assignment
                assignment.status = AssignmentStatus.REJECTED
                assignment.rejected_at = datetime.utcnow()
                
                # Update referee reliability
                self.matching_service.update_referee_reliability(
                    assignment.referee_id, 'rejected'
                )
                
                # Try to assign to backup
                backup = db.query(Assignment).filter(
                    Assignment.game_id == assignment.game_id,
                    Assignment.is_backup == True,
                    Assignment.status == AssignmentStatus.PENDING
                ).order_by(Assignment.match_score.desc()).first()
                
                if backup:
                    # Promote backup to primary
                    backup.is_backup = False
                    backup.status = AssignmentStatus.NOTIFIED
                    backup.notified_at = datetime.utcnow()
                    backup.response_deadline = datetime.utcnow() + timedelta(
                        hours=Config.CONFIRMATION_WINDOW_HOURS
                    )
                    
                    # Send notification to backup
                    self.notification_service.send_assignment_notification(backup)
                    self._schedule_confirmation_deadline(backup)
                else:
                    # No backup available, revert game to pending
                    game = db.query(Game).filter_by(id=assignment.game_id).first()
                    if game:
                        game.status = GameStatus.PENDING
                
                db.commit()
                
                logger.info(f"Assignment {assignment_id} rejected")
                return {'success': True}
                
        except Exception as e:
            logger.error(f"Error rejecting assignment: {str(e)}")
            return {'error': 'Failed to reject assignment'}
    
    def mark_completed(self, assignment_id: int) -> Dict:
        """Mark assignment as completed"""
        try:
            with get_db() as db:
                assignment = db.query(Assignment).filter_by(id=assignment_id).first()
                
                if not assignment:
                    return {'error': 'Assignment not found'}
                
                if assignment.status != AssignmentStatus.CONFIRMED:
                    return {'error': 'Only confirmed assignments can be completed'}
                
                # Check if game time has passed
                game = db.query(Game).filter_by(id=assignment.game_id).first()
                if game and game.scheduled_date > datetime.utcnow():
                    return {'error': 'Game has not occurred yet'}
                
                # Update assignment
                assignment.status = AssignmentStatus.COMPLETED
                assignment.completed_at = datetime.utcnow()
                
                # Update game status
                if game:
                    game.status = GameStatus.COMPLETED
                
                # Update referee stats
                referee = db.query(User).filter_by(id=assignment.referee_id).first()
                if referee:
                    referee.total_games_assigned += 1
                    referee.total_games_completed += 1
                    self.matching_service.update_referee_reliability(
                        assignment.referee_id, 'completed'
                    )
                
                db.commit()
                
                # Trigger payment processing
                from app.services.payment_service import PaymentService
                payment_service = PaymentService()
                payment_service.process_referee_payment(assignment_id)
                
                # Send review request
                from app.services.review_service import ReviewService
                review_service = ReviewService()
                review_service.send_review_request(assignment_id)
                
                logger.info(f"Assignment {assignment_id} marked as completed")
                return {'success': True}
                
        except Exception as e:
            logger.error(f"Error marking assignment completed: {str(e)}")
            return {'error': 'Failed to mark assignment completed'}
    
    def mark_no_show(self, assignment_id: int) -> Dict:
        """Mark assignment as no-show"""
        try:
            with get_db() as db:
                assignment = db.query(Assignment).filter_by(id=assignment_id).first()
                
                if not assignment:
                    return {'error': 'Assignment not found'}
                
                # Update assignment
                assignment.status = AssignmentStatus.NO_SHOW
                
                # Severe penalty for no-show
                self.matching_service.update_referee_reliability(
                    assignment.referee_id, 'no_show'
                )
                
                # Update referee stats
                referee = db.query(User).filter_by(id=assignment.referee_id).first()
                if referee:
                    referee.total_games_assigned += 1
                
                db.commit()
                
                # Notify admin
                self.notification_service.notify_admin_no_show(assignment)
                
                logger.warning(f"Assignment {assignment_id} marked as no-show")
                return {'success': True}
                
        except Exception as e:
            logger.error(f"Error marking no-show: {str(e)}")
            return {'error': 'Failed to mark no-show'}
    
    def _create_assignment(self, game: Game, referee: User, score: float, 
                          is_backup: bool = False) -> Assignment:
        """Create an assignment record"""
        try:
            assignment = self.assignment_db.create(
                game_id=game.id,
                referee_id=referee.id,
                status=AssignmentStatus.PENDING if is_backup else AssignmentStatus.NOTIFIED,
                is_backup=is_backup,
                match_score=score,
                distance_km=getattr(referee, 'distance_to_game', None),
                payment_amount=game.final_rate,
                notified_at=datetime.utcnow() if not is_backup else None,
                response_deadline=datetime.utcnow() + timedelta(
                    hours=Config.CONFIRMATION_WINDOW_HOURS
                ) if not is_backup else None
            )
            
            logger.info(f"Created {'backup' if is_backup else 'primary'} assignment {assignment.id}")
            return assignment
            
        except Exception as e:
            logger.error(f"Error creating assignment: {str(e)}")
            raise
    
    def _schedule_confirmation_deadline(self, assignment: Assignment):
        """Schedule actions for confirmation deadline"""
        try:
            # Schedule check at deadline
            self.scheduler.add_job(
                func=self._check_confirmation_deadline,
                trigger='date',
                run_date=assignment.response_deadline,
                args=[assignment.id],
                id=f'deadline_{assignment.id}'
            )
            
            # Schedule reminders
            reminder_times = [
                assignment.response_deadline - timedelta(hours=12),  # 12 hours before
                assignment.response_deadline - timedelta(hours=1)    # 1 hour before
            ]
            
            for i, reminder_time in enumerate(reminder_times):
                if reminder_time > datetime.utcnow():
                    self.scheduler.add_job(
                        func=self._send_confirmation_reminder,
                        trigger='date',
                        run_date=reminder_time,
                        args=[assignment.id, 12 if i == 0 else 1],
                        id=f'reminder_{assignment.id}_{i}'
                    )
                    
        except Exception as e:
            logger.error(f"Error scheduling confirmation deadline: {str(e)}")
    
    def _check_confirmation_deadline(self, assignment_id: int):
        """Check if assignment was confirmed by deadline"""
        try:
            with get_db() as db:
                assignment = db.query(Assignment).filter_by(id=assignment_id).first()
                
                if assignment and assignment.status == AssignmentStatus.NOTIFIED:
                    # No response, treat as rejection
                    assignment.status = AssignmentStatus.REJECTED
                    
                    # Update reliability
                    self.matching_service.update_referee_reliability(
                        assignment.referee_id, 'no_response'
                    )
                    
                    # Try backup assignment
                    # (Similar logic to reject_assignment)
                    
                    db.commit()
                    logger.warning(f"Assignment {assignment_id} expired without response")
                    
        except Exception as e:
            logger.error(f"Error checking confirmation deadline: {str(e)}")
    
    def _send_confirmation_reminder(self, assignment_id: int, hours_left: int):
        """Send confirmation reminder"""
        try:
            with get_db() as db:
                assignment = db.query(Assignment).filter_by(id=assignment_id).first()
                
                if assignment and assignment.status == AssignmentStatus.NOTIFIED:
                    self.notification_service.send_confirmation_reminder(assignment, hours_left)
                    
        except Exception as e:
            logger.error(f"Error sending confirmation reminder: {str(e)}")
    
    def _schedule_game_day_reminder(self, assignment: Assignment):
        """Schedule game day reminder"""
        try:
            with get_db() as db:
                game = db.query(Game).filter_by(id=assignment.game_id).first()
                
                if game:
                    # Send reminder 2 hours before game
                    reminder_time = game.scheduled_date - timedelta(hours=2)
                    
                    if reminder_time > datetime.utcnow():
                        self.scheduler.add_job(
                            func=self.notification_service.send_game_day_reminder,
                            trigger='date',
                            run_date=reminder_time,
                            args=[assignment.id],
                            id=f'gameday_{assignment.id}'
                        )
                        
        except Exception as e:
            logger.error(f"Error scheduling game day reminder: {str(e)}")