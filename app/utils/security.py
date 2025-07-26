import secrets
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError
from config.config import Config

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = Config.SECRET_KEY
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def generate_token(data: dict, expires_delta: timedelta = None) -> str:
    """Generate JWT token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=Config.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_verification_code(length: int = 6) -> str:
    """Generate random verification code"""
    return ''.join(secrets.choice('0123456789') for _ in range(length))


def generate_secure_token() -> str:
    """Generate secure random token"""
    return secrets.token_urlsafe(32)