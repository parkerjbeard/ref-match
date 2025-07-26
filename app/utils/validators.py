import re
from typing import Optional, Tuple


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not email:
        return False, "Email is required"
    if not re.match(pattern, email):
        return False, "Invalid email format"
    return True, None


def validate_phone(phone: str) -> Tuple[bool, Optional[str]]:
    """Validate phone number (US format)"""
    # Remove all non-digits
    digits = re.sub(r'\D', '', phone)
    
    # Check if it's a valid US phone number
    if len(digits) == 10:
        formatted = f"+1{digits}"
        return True, formatted
    elif len(digits) == 11 and digits[0] == '1':
        formatted = f"+{digits}"
        return True, formatted
    else:
        return False, "Invalid phone number. Please provide a valid US phone number"


def validate_location(address: str, city: str, state: str, zip_code: str) -> Tuple[bool, Optional[str]]:
    """Validate location fields"""
    if not all([address, city, state, zip_code]):
        return False, "All location fields are required"
    
    # Validate state (2-letter code)
    valid_states = [
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
    ]
    
    if state.upper() not in valid_states:
        return False, "Invalid state code"
    
    # Validate zip code
    if not re.match(r'^\d{5}(-\d{4})?$', zip_code):
        return False, "Invalid zip code format"
    
    return True, None


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    return True, None