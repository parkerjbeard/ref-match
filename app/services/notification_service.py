from datetime import datetime
from typing import Dict, Optional
from app.database import get_db
from app.models import Assignment, Game, User, Review
from app.integrations import TwilioClient, SendGridClient
from config.config import Config
from app.utils.logger import get_logger

logger = get_logger(__name__)


class NotificationService:
    """Service for handling all notifications"""
    
    def __init__(self):
        self.twilio = TwilioClient()
        self.sendgrid = SendGridClient()
    
    def send_assignment_notification(self, assignment: Assignment, is_emergency: bool = False):
        """Send assignment notification to referee"""
        try:
            with get_db() as db:
                # Get referee and game details
                referee = db.query(User).filter_by(id=assignment.referee_id).first()
                game = db.query(Game).filter_by(id=assignment.game_id).first()
                
                if not referee or not game:
                    logger.error("Missing referee or game for assignment notification")
                    return
                
                # Prepare game details
                game_details = {
                    'sport': game.sport.value.title(),
                    'date': game.scheduled_date.strftime('%B %d, %Y at %I:%M %p'),
                    'location': f"{game.venue_name or game.address}, {game.city}, {game.state}",
                    'home_team': game.home_team or 'TBD',
                    'away_team': game.away_team or 'TBD',
                    'rate': game.final_rate
                }
                
                if is_emergency:
                    game_details['rate'] = f"{game.final_rate} (includes surge pricing)"
                
                # Determine notification preferences
                if referee.notification_preferences.get('sms', True):
                    self._send_sms_assignment(referee.phone, game_details)
                
                if referee.notification_preferences.get('email', True):
                    self._send_email_assignment(
                        referee.email,
                        f"{referee.first_name} {referee.last_name}",
                        game_details,
                        assignment.id
                    )
                
                logger.info(f"Sent assignment notification for assignment {assignment.id}")
                
        except Exception as e:
            logger.error(f"Error sending assignment notification: {str(e)}")
    
    def send_confirmation_notification(self, assignment: Assignment):
        """Send confirmation notification"""
        try:
            with get_db() as db:
                referee = db.query(User).filter_by(id=assignment.referee_id).first()
                game = db.query(Game).filter_by(id=assignment.game_id).first()
                
                if not referee or not game:
                    return
                
                message = (
                    f"RefMatch: Your assignment for {game.sport.value.title()} on "
                    f"{game.scheduled_date.strftime('%B %d at %I:%M %p')} is confirmed! "
                    f"We'll send a reminder on game day."
                )
                
                if referee.notification_preferences.get('sms', True):
                    self.twilio.send_sms(referee.phone, message)
                
                logger.info(f"Sent confirmation notification for assignment {assignment.id}")
                
        except Exception as e:
            logger.error(f"Error sending confirmation notification: {str(e)}")
    
    def send_confirmation_reminder(self, assignment: Assignment, hours_left: int):
        """Send reminder to confirm assignment"""
        try:
            with get_db() as db:
                referee = db.query(User).filter_by(id=assignment.referee_id).first()
                game = db.query(Game).filter_by(id=assignment.game_id).first()
                
                if not referee or not game:
                    return
                
                game_details = {
                    'date': game.scheduled_date.strftime('%B %d at %I:%M %p'),
                    'location': f"{game.city}, {game.state}"
                }
                
                if referee.notification_preferences.get('sms', True):
                    self.twilio.send_reminder(referee.phone, game_details, hours_left)
                
                logger.info(f"Sent {hours_left}h reminder for assignment {assignment.id}")
                
        except Exception as e:
            logger.error(f"Error sending confirmation reminder: {str(e)}")
    
    def send_game_day_reminder(self, assignment_id: int):
        """Send game day reminder"""
        try:
            with get_db() as db:
                assignment = db.query(Assignment).filter_by(id=assignment_id).first()
                if not assignment:
                    return
                
                referee = db.query(User).filter_by(id=assignment.referee_id).first()
                game = db.query(Game).filter_by(id=assignment.game_id).first()
                
                if not referee or not game:
                    return
                
                game_details = {
                    'time': game.scheduled_date.strftime('%I:%M %p'),
                    'location': f"{game.venue_name or game.address}, {game.city}"
                }
                
                if referee.notification_preferences.get('sms', True):
                    self.twilio.send_game_day_reminder(referee.phone, game_details)
                
                logger.info(f"Sent game day reminder for assignment {assignment_id}")
                
        except Exception as e:
            logger.error(f"Error sending game day reminder: {str(e)}")
    
    def send_payment_notification(self, referee_id: int, amount: float):
        """Send payment notification"""
        try:
            with get_db() as db:
                referee = db.query(User).filter_by(id=referee_id).first()
                
                if not referee:
                    return
                
                if referee.notification_preferences.get('sms', True):
                    self.twilio.send_payment_notification(referee.phone, amount)
                
                if referee.notification_preferences.get('email', True):
                    payment_details = {
                        'amount': amount,
                        'type': 'Game Payment',
                        'date': datetime.utcnow().strftime('%B %d, %Y'),
                        'transaction_id': f"PAY-{datetime.utcnow().timestamp()}"
                    }
                    
                    self.sendgrid.send_payment_receipt(
                        referee.email,
                        f"{referee.first_name} {referee.last_name}",
                        payment_details
                    )
                
                logger.info(f"Sent payment notification to referee {referee_id}")
                
        except Exception as e:
            logger.error(f"Error sending payment notification: {str(e)}")
    
    def send_review_request(self, review_id: int):
        """Send review request to coach"""
        try:
            with get_db() as db:
                review = db.query(Review).filter_by(id=review_id).first()
                if not review:
                    return
                
                coach = db.query(User).filter_by(id=review.reviewer_id).first()
                referee = db.query(User).filter_by(id=review.referee_id).first()
                assignment = db.query(Assignment).filter_by(id=review.assignment_id).first()
                game = db.query(Game).filter_by(id=assignment.game_id).first()
                
                if not all([coach, referee, assignment, game]):
                    return
                
                game_details = {
                    'home_team': game.home_team,
                    'away_team': game.away_team,
                    'date': game.scheduled_date.strftime('%B %d, %Y')
                }
                
                review_link = f"{Config.APP_URL}/review/{review.id}"
                
                self.sendgrid.send_review_request(
                    coach.email,
                    f"{coach.first_name} {coach.last_name}",
                    f"{referee.first_name} {referee.last_name}",
                    game_details,
                    review_link
                )
                
                logger.info(f"Sent review request {review_id}")
                
        except Exception as e:
            logger.error(f"Error sending review request: {str(e)}")
    
    def notify_admin_no_show(self, assignment: Assignment):
        """Notify admin of referee no-show"""
        try:
            with get_db() as db:
                referee = db.query(User).filter_by(id=assignment.referee_id).first()
                game = db.query(Game).filter_by(id=assignment.game_id).first()
                
                if not referee or not game:
                    return
                
                subject = f"URGENT: Referee No-Show - {game.sport.value.title()}"
                content = f"""
                Referee No-Show Alert:
                
                Referee: {referee.first_name} {referee.last_name} (ID: {referee.id})
                Game: {game.home_team} vs {game.away_team}
                Date: {game.scheduled_date.strftime('%B %d, %Y at %I:%M %p')}
                Location: {game.venue_name or game.address}, {game.city}
                
                This referee's reliability score has been updated.
                Current no-show count: {referee.no_show_count}
                
                Please follow up with the organizer and referee.
                """
                
                # Send to admin email
                self.sendgrid.send_email(
                    Config.ADMIN_EMAIL,
                    subject,
                    f"<pre>{content}</pre>",
                    content
                )
                
                # Also send SMS if configured
                if Config.ADMIN_PHONE:
                    self.twilio.send_sms(
                        Config.ADMIN_PHONE,
                        f"URGENT: Referee no-show for {game.sport.value} game. Check email for details."
                    )
                
                logger.warning(f"Notified admin of no-show for assignment {assignment.id}")
                
        except Exception as e:
            logger.error(f"Error notifying admin of no-show: {str(e)}")
    
    def _send_sms_assignment(self, phone: str, game_details: Dict):
        """Send SMS assignment notification"""
        try:
            confirmation_url = f"{Config.APP_URL}/assignment/confirm"
            self.twilio.send_assignment_notification(phone, game_details, confirmation_url)
        except Exception as e:
            logger.error(f"Error sending SMS assignment: {str(e)}")
    
    def _send_email_assignment(self, email: str, name: str, game_details: Dict, assignment_id: int):
        """Send email assignment notification"""
        try:
            confirmation_link = f"{Config.APP_URL}/assignment/{assignment_id}/confirm"
            self.sendgrid.send_assignment_email(email, name, game_details, confirmation_link)
        except Exception as e:
            logger.error(f"Error sending email assignment: {str(e)}")