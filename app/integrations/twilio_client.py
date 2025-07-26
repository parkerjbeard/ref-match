from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from typing import Optional, Dict
from config.config import Config
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TwilioClient:
    """Wrapper for Twilio SMS operations"""
    
    def __init__(self):
        self.account_sid = Config.TWILIO_ACCOUNT_SID
        self.auth_token = Config.TWILIO_AUTH_TOKEN
        self.phone_number = Config.TWILIO_PHONE_NUMBER
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None
            logger.warning("Twilio credentials not configured")
    
    def send_sms(self, to_number: str, message: str, callback_url: str = None) -> Optional[Dict]:
        """Send SMS message"""
        if not self.client:
            logger.error("Twilio client not initialized")
            return None
            
        try:
            message_data = {
                'body': message,
                'from_': self.phone_number,
                'to': to_number
            }
            
            if callback_url:
                message_data['status_callback'] = callback_url
                
            message = self.client.messages.create(**message_data)
            
            return {
                'sid': message.sid,
                'status': message.status,
                'to': message.to,
                'from': message.from_,
                'body': message.body,
                'date_sent': message.date_sent
            }
        except TwilioRestException as e:
            logger.error(f"Error sending SMS to {to_number}: {str(e)}")
            return None
    
    def send_verification_code(self, to_number: str, code: str) -> Optional[Dict]:
        """Send verification code via SMS"""
        message = f"Your RefMatch verification code is: {code}. This code expires in 10 minutes."
        return self.send_sms(to_number, message)
    
    def send_assignment_notification(self, to_number: str, game_details: Dict, 
                                   confirmation_url: str = None) -> Optional[Dict]:
        """Send game assignment notification"""
        message = (
            f"RefMatch: New game assignment!\n"
            f"Sport: {game_details['sport']}\n"
            f"Date: {game_details['date']}\n"
            f"Location: {game_details['location']}\n"
            f"Rate: ${game_details['rate']}\n\n"
            f"Reply YES to confirm or NO to decline."
        )
        
        if confirmation_url:
            message += f"\n\nOr confirm at: {confirmation_url}"
            
        return self.send_sms(to_number, message)
    
    def send_reminder(self, to_number: str, game_details: Dict, hours_left: int) -> Optional[Dict]:
        """Send assignment reminder"""
        message = (
            f"RefMatch Reminder: You have {hours_left} hours to confirm your assignment.\n"
            f"Game: {game_details['date']} at {game_details['location']}\n"
            f"Reply YES to confirm or NO to decline."
        )
        return self.send_sms(to_number, message)
    
    def send_game_day_reminder(self, to_number: str, game_details: Dict) -> Optional[Dict]:
        """Send game day reminder"""
        message = (
            f"RefMatch: Game day reminder!\n"
            f"Today at {game_details['time']}\n"
            f"Location: {game_details['location']}\n"
            f"Arrive 30 minutes early for preparation."
        )
        return self.send_sms(to_number, message)
    
    def send_payment_notification(self, to_number: str, amount: float) -> Optional[Dict]:
        """Send payment notification"""
        message = f"RefMatch: Payment of ${amount:.2f} has been processed to your account. Thank you for your service!"
        return self.send_sms(to_number, message)
    
    def parse_sms_response(self, body: str) -> str:
        """Parse SMS response to extract confirmation"""
        body = body.strip().upper()
        
        # Check for clear YES/NO responses
        if body in ['YES', 'Y', 'CONFIRM', 'ACCEPT']:
            return 'CONFIRMED'
        elif body in ['NO', 'N', 'DECLINE', 'REJECT']:
            return 'REJECTED'
        else:
            return 'UNCLEAR'
    
    def get_message_status(self, message_sid: str) -> Optional[str]:
        """Get status of a sent message"""
        if not self.client:
            return None
            
        try:
            message = self.client.messages(message_sid).fetch()
            return message.status
        except TwilioRestException as e:
            logger.error(f"Error fetching message status: {str(e)}")
            return None