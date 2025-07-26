from datetime import datetime
from app.database import DatabaseManager, get_db
from app.models import User, Payment, Assignment, BackgroundCheck
from app.models.assignment import AssignmentStatus
from app.models.payment import PaymentStatus
from app.integrations import TwilioClient
from app.services.assignment_service import AssignmentService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class WebhookService:
    """Service for handling webhook events"""
    
    def __init__(self):
        self.user_db = DatabaseManager(User)
        self.payment_db = DatabaseManager(Payment)
        self.assignment_db = DatabaseManager(Assignment)
        self.background_check_db = DatabaseManager(BackgroundCheck)
        self.twilio_client = TwilioClient()
        self.assignment_service = AssignmentService()
    
    def process_stripe_event(self, event: dict) -> dict:
        """Process Stripe webhook events"""
        event_type = event.get('type')
        data = event.get('data', {}).get('object', {})
        
        logger.info(f"Processing Stripe event: {event_type}")
        
        if event_type == 'payment_intent.succeeded':
            # Handle successful payment
            payment_intent_id = data.get('id')
            amount = data.get('amount') / 100  # Convert cents to dollars
            
            # Find and update payment record
            with get_db() as db:
                payment = db.query(Payment).filter_by(
                    stripe_payment_intent_id=payment_intent_id
                ).first()
                
                if payment:
                    payment.status = PaymentStatus.COMPLETED
                    payment.processed_at = datetime.utcnow()
                    db.commit()
                    
                    logger.info(f"Payment {payment.id} marked as completed")
                    return {'payment_id': payment.id, 'status': 'completed'}
        
        elif event_type == 'payment_intent.payment_failed':
            # Handle failed payment
            payment_intent_id = data.get('id')
            
            with get_db() as db:
                payment = db.query(Payment).filter_by(
                    stripe_payment_intent_id=payment_intent_id
                ).first()
                
                if payment:
                    payment.status = PaymentStatus.FAILED
                    payment.failed_at = datetime.utcnow()
                    payment.failure_reason = data.get('last_payment_error', {}).get('message')
                    db.commit()
                    
                    logger.error(f"Payment {payment.id} failed")
                    return {'payment_id': payment.id, 'status': 'failed'}
        
        elif event_type == 'payout.paid':
            # Handle successful referee payout
            payout_id = data.get('id')
            amount = data.get('amount') / 100
            
            logger.info(f"Payout {payout_id} completed: ${amount}")
            return {'payout_id': payout_id, 'status': 'paid'}
        
        elif event_type == 'account.updated':
            # Handle connected account updates
            account_id = data.get('id')
            logger.info(f"Connected account {account_id} updated")
            return {'account_id': account_id, 'status': 'updated'}
        
        return {'event_type': event_type, 'processed': True}
    
    def process_checkr_event(self, webhook_data: dict) -> dict:
        """Process Checkr webhook events"""
        event_type = webhook_data.get('type')
        data = webhook_data.get('data', {})
        
        logger.info(f"Processing Checkr event: {event_type}")
        
        if event_type == 'report.completed':
            # Background check completed
            report_id = data.get('object', {}).get('id')
            candidate_id = data.get('object', {}).get('candidate_id')
            
            with get_db() as db:
                # Find background check record
                bg_check = db.query(BackgroundCheck).filter_by(
                    checkr_report_id=report_id
                ).first()
                
                if bg_check:
                    # Parse report status
                    from app.integrations import CheckrClient
                    checkr = CheckrClient()
                    report = checkr.get_report(report_id)
                    status = checkr.parse_report_status(report)
                    
                    # Update background check
                    bg_check.status = status
                    bg_check.completed_at = datetime.utcnow()
                    bg_check.report_data = report
                    
                    # Update user status if clear
                    if status == 'clear':
                        user = db.query(User).filter_by(id=bg_check.user_id).first()
                        if user:
                            user.background_check_status = 'clear'
                            user.is_active = True
                    
                    db.commit()
                    logger.info(f"Background check {bg_check.id} completed with status: {status}")
                    
                    return {'background_check_id': bg_check.id, 'status': status}
        
        elif event_type == 'invitation.completed':
            # Candidate completed invitation
            invitation_id = data.get('object', {}).get('id')
            candidate_id = data.get('object', {}).get('candidate_id')
            
            logger.info(f"Checkr invitation {invitation_id} completed")
            # Could trigger report creation here
            
            return {'invitation_id': invitation_id, 'action': 'create_report'}
        
        return {'event_type': event_type, 'processed': True}
    
    def process_sms_response(self, from_number: str, body: str, message_sid: str) -> dict:
        """Process incoming SMS responses"""
        # Parse response
        response_type = self.twilio_client.parse_sms_response(body)
        
        logger.info(f"SMS response from {from_number}: {response_type}")
        
        if response_type in ['CONFIRMED', 'REJECTED']:
            # Find user by phone number
            user = self.user_db.get_by(phone=from_number)
            
            if user:
                # Find pending assignment for this referee
                with get_db() as db:
                    assignment = db.query(Assignment).filter_by(
                        referee_id=user.id,
                        status=AssignmentStatus.NOTIFIED
                    ).order_by(Assignment.notified_at.desc()).first()
                    
                    if assignment:
                        if response_type == 'CONFIRMED':
                            # Confirm assignment
                            self.assignment_service.confirm_assignment(assignment.id)
                            
                            # Send confirmation SMS
                            self.twilio_client.send_sms(
                                from_number,
                                "Great! You're confirmed for the game. We'll send a reminder on game day."
                            )
                        else:
                            # Reject assignment
                            self.assignment_service.reject_assignment(assignment.id)
                            
                            # Send acknowledgment
                            self.twilio_client.send_sms(
                                from_number,
                                "Thanks for letting us know. We'll find another referee."
                            )
                        
                        return {
                            'assignment_id': assignment.id,
                            'response': response_type,
                            'processed': True
                        }
        
        elif response_type == 'UNCLEAR':
            # Send clarification request
            self.twilio_client.send_sms(
                from_number,
                "Sorry, we didn't understand. Please reply YES to accept or NO to decline the assignment."
            )
        
        return {'response': response_type, 'processed': True}
    
    def update_sms_status(self, message_sid: str, status: str, error_code: str = None):
        """Update SMS delivery status"""
        # Could store message delivery status in database
        if error_code:
            logger.error(f"SMS {message_sid} failed with error: {error_code}")
        else:
            logger.info(f"SMS {message_sid} status: {status}")
    
    def process_email_event(self, event: dict):
        """Process SendGrid email events"""
        event_type = event.get('event')
        email = event.get('email')
        
        # Handle different email events
        if event_type == 'bounce':
            logger.warning(f"Email bounced: {email}")
            # Could mark email as invalid in user record
            
        elif event_type == 'delivered':
            logger.info(f"Email delivered: {email}")
            
        elif event_type == 'open':
            logger.info(f"Email opened: {email}")
            
        elif event_type == 'click':
            url = event.get('url')
            logger.info(f"Email link clicked: {email} - {url}")