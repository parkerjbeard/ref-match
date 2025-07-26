from datetime import datetime, timedelta
from typing import Dict, Optional
from app.database import DatabaseManager, get_db
from app.models import User
from app.models.user import UserRole
from app.utils.security import hash_password, verify_password, generate_token, verify_token
from app.integrations import TwilioClient, SendGridClient, CheckrClient
from config.config import Config
from app.utils.logger import get_logger
import random
import string

logger = get_logger(__name__)


class AuthService:
    """Service for handling authentication"""
    
    def __init__(self):
        self.user_db = DatabaseManager(User)
        self.twilio = TwilioClient()
        self.sendgrid = SendGridClient()
        self.checkr = CheckrClient()
    
    def register_user(self, data: Dict) -> Dict:
        """Register a new user"""
        try:
            # Check if user already exists
            existing_user = self.user_db.get_by(email=data['email'])
            if existing_user:
                return {'error': 'Email already registered'}
            
            existing_phone = self.user_db.get_by(phone=data['phone'])
            if existing_phone:
                return {'error': 'Phone number already registered'}
            
            # Hash password
            password_hash = hash_password(data['password'])
            
            # Prepare user data
            user_data = {
                'email': data['email'],
                'phone': data['phone'],
                'password_hash': password_hash,
                'first_name': data['first_name'],
                'last_name': data['last_name'],
                'role': UserRole[data['role'].upper()],
                'address': data.get('address'),
                'city': data.get('city'),
                'state': data.get('state'),
                'zip_code': data.get('zip_code'),
                'is_active': False,  # Require email verification
                'is_verified': False
            }
            
            # Add organizer-specific fields
            if data['role'] == 'organizer':
                user_data.update({
                    'organization_name': data.get('organization_name'),
                    'organization_type': data.get('organization_type', 'school')
                })
            
            # Create user
            user = self.user_db.create(**user_data)
            
            # Send verification email
            self._send_verification_email(user)
            
            # For referees, initiate background check
            if user.role == UserRole.REFEREE:
                self._initiate_background_check(user)
            
            return {'user_id': user.id, 'success': True}
            
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return {'error': 'Registration failed'}
    
    def authenticate_user(self, email: str, password: str) -> Dict:
        """Authenticate user and return token"""
        try:
            # Use database session context
            with get_db() as db:
                user = db.query(User).filter(User.email == email).first()
                
                if not user:
                    return {'error': 'Invalid credentials'}
                
                if not verify_password(password, user.password_hash):
                    return {'error': 'Invalid credentials'}
                
                if not user.is_active:
                    return {'error': 'Account not activated'}
                
                # Generate access token
                token_data = {
                    'user_id': user.id,
                    'email': user.email,
                    'role': user.role.value
                }
                access_token = generate_token(token_data)
                
                return {
                    'access_token': access_token,
                    'user': {
                        'id': user.id,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'role': user.role.value
                    }
                }
            
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return {'error': 'Authentication failed'}
    
    def verify_email(self, token: str) -> Dict:
        """Verify email with token"""
        try:
            # Verify token
            payload = verify_token(token)
            if not payload or payload.get('type') != 'email_verification':
                return {'error': 'Invalid or expired token'}
            
            user_id = payload.get('user_id')
            user = self.user_db.get(user_id)
            
            if not user:
                return {'error': 'User not found'}
            
            # Update user status
            self.user_db.update(user_id, email_verified=True, is_active=True)
            
            return {'success': True, 'message': 'Email verified successfully'}
            
        except Exception as e:
            logger.error(f"Email verification error: {str(e)}")
            return {'error': 'Verification failed'}
    
    def send_phone_verification(self, user_id: int) -> Dict:
        """Send phone verification code"""
        try:
            user = self.user_db.get(user_id)
            if not user:
                return {'error': 'User not found'}
            
            # Generate 6-digit code
            code = ''.join(random.choices(string.digits, k=6))
            
            # Store code (in production, use Redis or similar)
            # For now, we'll store in session or temporary storage
            self._store_verification_code(user_id, code)
            
            # Send SMS
            self.twilio.send_sms(
                user.phone,
                f"Your RefMatch verification code is: {code}"
            )
            
            return {'success': True, 'message': 'Verification code sent'}
            
        except Exception as e:
            logger.error(f"Phone verification error: {str(e)}")
            return {'error': 'Failed to send verification code'}
    
    def verify_phone(self, user_id: int, code: str) -> Dict:
        """Verify phone with code"""
        try:
            # Verify code (simplified for MVP)
            stored_code = self._get_verification_code(user_id)
            
            if not stored_code or stored_code != code:
                return {'error': 'Invalid verification code'}
            
            # Update user status
            self.user_db.update(user_id, phone_verified=True)
            
            return {'success': True, 'message': 'Phone verified successfully'}
            
        except Exception as e:
            logger.error(f"Phone verification error: {str(e)}")
            return {'error': 'Verification failed'}
    
    def refresh_token(self, token: str) -> Dict:
        """Refresh access token"""
        try:
            payload = verify_token(token)
            if not payload:
                return {'error': 'Invalid token'}
            
            # Generate new token
            new_token = generate_token({
                'user_id': payload['user_id'],
                'email': payload['email'],
                'role': payload['role']
            })
            
            return {'access_token': new_token}
            
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            return {'error': 'Token refresh failed'}
    
    def _send_verification_email(self, user):
        """Send email verification"""
        try:
            # Generate verification token
            token_data = {
                'user_id': user.id,
                'email': user.email,
                'type': 'email_verification'
            }
            token = generate_token(token_data, expires_delta=timedelta(hours=24))
            
            # Create verification URL
            verify_url = f"{Config.APP_URL}/verify-email/{token}"
            
            # Send email
            self.sendgrid.send_email(
                to_email=user.email,
                subject="Verify your RefMatch account",
                html_content=f"""
                <h2>Welcome to RefMatch!</h2>
                <p>Please click the link below to verify your email address:</p>
                <a href="{verify_url}">Verify Email</a>
                <p>This link will expire in 24 hours.</p>
                """
            )
            
        except Exception as e:
            logger.error(f"Email sending error: {str(e)}")
    
    def _initiate_background_check(self, user):
        """Initiate background check for referee"""
        try:
            # Create background check request
            self.checkr.create_candidate({
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'phone': user.phone,
                'user_id': user.id
            })
            
        except Exception as e:
            logger.error(f"Background check initiation error: {str(e)}")
    
    def _store_verification_code(self, user_id: int, code: str):
        """Store verification code (simplified for MVP)"""
        # In production, use Redis or similar
        # For MVP, we'll use a simple in-memory store
        if not hasattr(self, '_verification_codes'):
            self._verification_codes = {}
        self._verification_codes[user_id] = {
            'code': code,
            'timestamp': datetime.utcnow()
        }
    
    def _get_verification_code(self, user_id: int) -> Optional[str]:
        """Get stored verification code"""
        if not hasattr(self, '_verification_codes'):
            return None
        
        data = self._verification_codes.get(user_id)
        if not data:
            return None
        
        # Check if code is expired (10 minutes)
        if datetime.utcnow() - data['timestamp'] > timedelta(minutes=10):
            del self._verification_codes[user_id]
            return None
        
        return data['code']