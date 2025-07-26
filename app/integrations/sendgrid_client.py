import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType
import base64
from typing import List, Optional, Dict
from config.config import Config
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SendGridClient:
    """Wrapper for SendGrid email operations"""
    
    def __init__(self):
        self.api_key = Config.SENDGRID_API_KEY
        self.from_email = Config.SENDGRID_FROM_EMAIL
        
        if self.api_key:
            self.client = sendgrid.SendGridAPIClient(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("SendGrid API key not configured")
    
    def send_email(self, to_email: str, subject: str, html_content: str, 
                   plain_content: str = None, attachments: List[Dict] = None) -> Optional[Dict]:
        """Send email via SendGrid"""
        if not self.client:
            logger.error("SendGrid client not initialized")
            return None
            
        try:
            message = Mail(
                from_email=Email(self.from_email, "RefMatch"),
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            
            if plain_content:
                message.plain_text_content = Content("text/plain", plain_content)
            
            # Add attachments if any
            if attachments:
                for att in attachments:
                    attachment = Attachment(
                        FileContent(att['content']),
                        FileName(att['filename']),
                        FileType(att['type'])
                    )
                    message.add_attachment(attachment)
            
            response = self.client.send(message)
            
            return {
                'status_code': response.status_code,
                'message_id': response.headers.get('X-Message-Id')
            }
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            return None
    
    def send_verification_email(self, to_email: str, name: str, verification_link: str) -> Optional[Dict]:
        """Send email verification"""
        subject = "Verify your RefMatch account"
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2>Welcome to RefMatch, {name}!</h2>
                <p>Please verify your email address to complete your registration.</p>
                <p style="margin: 30px 0;">
                    <a href="{verification_link}" 
                       style="background-color: #4CAF50; color: white; padding: 14px 28px; 
                              text-decoration: none; border-radius: 4px; display: inline-block;">
                        Verify Email
                    </a>
                </p>
                <p>Or copy and paste this link: {verification_link}</p>
                <p>This link expires in 48 hours.</p>
                <hr style="margin-top: 40px;">
                <p style="color: #666; font-size: 12px;">
                    If you didn't create a RefMatch account, please ignore this email.
                </p>
            </body>
        </html>
        """
        plain_content = f"""
        Welcome to RefMatch, {name}!
        
        Please verify your email address by clicking the link below:
        {verification_link}
        
        This link expires in 48 hours.
        
        If you didn't create a RefMatch account, please ignore this email.
        """
        
        return self.send_email(to_email, subject, html_content, plain_content)
    
    def send_quiz_link(self, to_email: str, name: str, sport: str, level: str, quiz_link: str) -> Optional[Dict]:
        """Send certification quiz link"""
        subject = f"RefMatch Certification Quiz - {sport.title()} ({level.title()})"
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2>Certification Quiz Ready</h2>
                <p>Hi {name},</p>
                <p>Your {sport.title()} certification quiz ({level.title()} level) is ready!</p>
                <ul>
                    <li>Number of questions: {Config.QUIZ_QUESTIONS_PER_TEST}</li>
                    <li>Passing score: {int(Config.QUIZ_PASS_THRESHOLD * 100)}%</li>
                    <li>Time limit: None - take your time</li>
                </ul>
                <p style="margin: 30px 0;">
                    <a href="{quiz_link}" 
                       style="background-color: #2196F3; color: white; padding: 14px 28px; 
                              text-decoration: none; border-radius: 4px; display: inline-block;">
                        Start Quiz
                    </a>
                </p>
                <p>Good luck!</p>
            </body>
        </html>
        """
        
        return self.send_email(to_email, subject, html_content)
    
    def send_assignment_email(self, to_email: str, name: str, game_details: Dict, 
                            confirmation_link: str) -> Optional[Dict]:
        """Send game assignment notification email"""
        subject = f"New Game Assignment - {game_details['date']}"
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2>New Game Assignment</h2>
                <p>Hi {name},</p>
                <p>You've been selected for a new game assignment:</p>
                <div style="background-color: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <p><strong>Sport:</strong> {game_details['sport']}</p>
                    <p><strong>Date & Time:</strong> {game_details['date']}</p>
                    <p><strong>Location:</strong> {game_details['location']}</p>
                    <p><strong>Teams:</strong> {game_details['home_team']} vs {game_details['away_team']}</p>
                    <p><strong>Rate:</strong> ${game_details['rate']}</p>
                </div>
                <p>Please confirm your availability within 24 hours:</p>
                <p style="margin: 30px 0;">
                    <a href="{confirmation_link}?response=accept" 
                       style="background-color: #4CAF50; color: white; padding: 14px 28px; 
                              text-decoration: none; border-radius: 4px; display: inline-block; margin-right: 10px;">
                        Accept
                    </a>
                    <a href="{confirmation_link}?response=decline" 
                       style="background-color: #f44336; color: white; padding: 14px 28px; 
                              text-decoration: none; border-radius: 4px; display: inline-block;">
                        Decline
                    </a>
                </p>
                <p>Or reply to the SMS notification with YES or NO.</p>
            </body>
        </html>
        """
        
        return self.send_email(to_email, subject, html_content)
    
    def send_review_request(self, to_email: str, coach_name: str, referee_name: str, 
                          game_details: Dict, review_link: str) -> Optional[Dict]:
        """Send review request to coach"""
        subject = f"Please Review Referee Performance - {game_details['date']}"
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2>Referee Performance Review</h2>
                <p>Hi {coach_name},</p>
                <p>Please take a moment to review the referee's performance from your recent game:</p>
                <div style="background-color: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <p><strong>Referee:</strong> {referee_name}</p>
                    <p><strong>Game:</strong> {game_details['home_team']} vs {game_details['away_team']}</p>
                    <p><strong>Date:</strong> {game_details['date']}</p>
                </div>
                <p style="margin: 30px 0;">
                    <a href="{review_link}" 
                       style="background-color: #FF9800; color: white; padding: 14px 28px; 
                              text-decoration: none; border-radius: 4px; display: inline-block;">
                        Submit Review
                    </a>
                </p>
                <p>Your feedback helps us maintain high officiating standards.</p>
                <p style="color: #666; font-size: 12px; margin-top: 40px;">
                    This review link expires in 7 days.
                </p>
            </body>
        </html>
        """
        
        return self.send_email(to_email, subject, html_content)
    
    def send_payment_receipt(self, to_email: str, name: str, payment_details: Dict) -> Optional[Dict]:
        """Send payment receipt"""
        subject = f"Payment Receipt - RefMatch"
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2>Payment Receipt</h2>
                <p>Hi {name},</p>
                <p>Your payment has been processed successfully.</p>
                <div style="background-color: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <p><strong>Amount:</strong> ${payment_details['amount']:.2f}</p>
                    <p><strong>Type:</strong> {payment_details['type']}</p>
                    <p><strong>Date:</strong> {payment_details['date']}</p>
                    <p><strong>Transaction ID:</strong> {payment_details['transaction_id']}</p>
                </div>
                <p>Thank you for using RefMatch!</p>
            </body>
        </html>
        """
        
        return self.send_email(to_email, subject, html_content)