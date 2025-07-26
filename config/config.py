import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DATABASE_URL = os.environ.get('DATABASE_URL') or 'sqlite:///refmatch.db'
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # API Keys
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
    SENDGRID_FROM_EMAIL = os.environ.get('SENDGRID_FROM_EMAIL', 'noreply@refmatch.com')
    CHECKR_API_KEY = os.environ.get('CHECKR_API_KEY')
    
    # Application Settings
    APP_URL = os.environ.get('APP_URL', 'http://localhost:5000')
    PLATFORM_FEE_PERCENTAGE = float(os.environ.get('PLATFORM_FEE_PERCENTAGE', '0.15'))
    MAX_DISTANCE_KM = int(os.environ.get('MAX_DISTANCE_KM', '50'))
    SURGE_PRICING_CAP = float(os.environ.get('SURGE_PRICING_CAP', '1.5'))
    CONFIRMATION_WINDOW_HOURS = int(os.environ.get('CONFIRMATION_WINDOW_HOURS', '24'))
    
    # Admin Settings
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@refmatch.com')
    ADMIN_PHONE = os.environ.get('ADMIN_PHONE')
    
    # Rate Limiting
    RATE_LIMIT_PER_HOUR = int(os.environ.get('RATE_LIMIT_PER_HOUR', '100'))
    
    # Token Settings
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
    VERIFICATION_TOKEN_EXPIRE_HOURS = 48
    
    # Base Rates per Sport/Tier (in dollars)
    BASE_RATES = {
        'basketball': {'entry': 50, 'intermediate': 75, 'advanced': 100},
        'football': {'entry': 60, 'intermediate': 85, 'advanced': 120},
        'soccer': {'entry': 45, 'intermediate': 70, 'advanced': 95},
        'softball': {'entry': 40, 'intermediate': 65, 'advanced': 85},
        'volleyball': {'entry': 40, 'intermediate': 60, 'advanced': 80},
        'baseball': {'entry': 45, 'intermediate': 70, 'advanced': 95}
    }
    
    # Quiz Settings
    QUIZ_PASS_THRESHOLD = 0.8  # 80%
    QUIZ_QUESTIONS_PER_TEST = 15
    
    # Logging
    LOG_FILE = 'logs/refmatch.log'
    LOG_LEVEL = 'INFO'


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    DEBUG = True
    TESTING = True
    DATABASE_URL = 'sqlite:///test_refmatch.db'
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}