import pytest
from app.services.auth_service import AuthService
from app.database import drop_db, init_db
from app.models.user import UserRole


@pytest.fixture
def auth_service():
    """Create auth service instance"""
    init_db()
    yield AuthService()
    drop_db()


class TestAuthService:
    """Test authentication service"""
    
    def test_register_referee(self, auth_service):
        """Test referee registration"""
        user_data = {
            'email': 'test.referee@example.com',
            'phone': '555-123-4567',
            'password': 'SecurePass123',
            'first_name': 'John',
            'last_name': 'Doe',
            'role': 'referee',
            'address': '123 Main St',
            'city': 'Phoenix',
            'state': 'AZ',
            'zip_code': '85001'
        }
        
        result = auth_service.register_user(user_data)
        assert 'user_id' in result
        assert result['success'] is True
    
    def test_register_duplicate_email(self, auth_service):
        """Test duplicate email registration"""
        user_data = {
            'email': 'duplicate@example.com',
            'phone': '555-123-4567',
            'password': 'SecurePass123',
            'first_name': 'John',
            'last_name': 'Doe',
            'role': 'referee'
        }
        
        # First registration
        auth_service.register_user(user_data)
        
        # Duplicate registration
        user_data['phone'] = '555-987-6543'  # Different phone
        result = auth_service.register_user(user_data)
        assert result.get('error') == 'Email already registered'
    
    def test_authenticate_user(self, auth_service):
        """Test user authentication"""
        # Register user
        user_data = {
            'email': 'auth.test@example.com',
            'phone': '555-123-4567',
            'password': 'SecurePass123',
            'first_name': 'Jane',
            'last_name': 'Smith',
            'role': 'organizer',
            'organization_name': 'Test School'
        }
        
        auth_service.register_user(user_data)
        
        # Activate user manually for testing
        from app.database import DatabaseManager
        from app.models import User
        user_db = DatabaseManager(User)
        user = user_db.get_by(email=user_data['email'])
        user_db.update(user.id, is_active=True, email_verified=True)
        
        # Test authentication
        result = auth_service.authenticate_user(user_data['email'], user_data['password'])
        assert 'access_token' in result
        assert result['user']['email'] == user_data['email']
    
    def test_invalid_credentials(self, auth_service):
        """Test authentication with invalid credentials"""
        result = auth_service.authenticate_user('nonexistent@example.com', 'wrongpass')
        assert result.get('error') == 'Invalid credentials'
    
    def test_phone_verification_flow(self, auth_service):
        """Test phone verification process"""
        # Register user
        user_data = {
            'email': 'phone.test@example.com',
            'phone': '+15551234567',
            'password': 'SecurePass123',
            'first_name': 'Phone',
            'last_name': 'Test',
            'role': 'referee'
        }
        
        auth_service.register_user(user_data)
        
        # Mock sending verification code
        result = auth_service.send_phone_verification(user_data['phone'])
        
        # In testing, we can access the internal verification codes
        code = auth_service._verification_codes.get(user_data['phone'])
        assert code is not None
        
        # Verify with correct code
        result = auth_service.verify_phone(user_data['phone'], code['code'])
        assert result.get('success') is True
    
    def test_token_refresh(self, auth_service):
        """Test token refresh"""
        # Create a token
        from app.utils.security import generate_token
        token_data = {
            'user_id': 1,
            'email': 'test@example.com',
            'role': 'referee'
        }
        token = generate_token(token_data)
        
        # Refresh token
        result = auth_service.refresh_token(token)
        assert 'access_token' in result
        assert result['access_token'] != token  # New token generated