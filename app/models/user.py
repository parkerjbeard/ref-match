from sqlalchemy import Column, String, Float, Boolean, Enum, JSON, Integer
from sqlalchemy.orm import relationship
import enum
from .base import BaseModel


class UserRole(enum.Enum):
    REFEREE = "referee"
    ORGANIZER = "organizer"
    COACH = "coach"
    ADMIN = "admin"


class User(BaseModel):
    __tablename__ = 'users'
    
    # Basic Info
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    
    # Location
    address = Column(String(500))
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Status
    is_active = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    background_check_status = Column(String(50), default='pending')
    
    # Referee-specific fields
    reliability_score = Column(Float, default=1.0)
    total_games_assigned = Column(Integer, default=0)
    total_games_completed = Column(Integer, default=0)
    no_show_count = Column(Integer, default=0)
    emergency_pool_opt_in = Column(Boolean, default=False)
    travel_distance_km = Column(Integer, default=50)
    
    # Organizer-specific fields
    organization_name = Column(String(255))
    organization_type = Column(String(50))  # school, league, etc.
    stripe_customer_id = Column(String(255))
    
    # Preferences
    notification_preferences = Column(JSON, default=lambda: {"sms": True, "email": True})
    
    # Relationships
    certifications = relationship("Certification", back_populates="referee", lazy='dynamic')
    assignments = relationship("Assignment", back_populates="referee", lazy='dynamic', foreign_keys='Assignment.referee_id')
    availabilities = relationship("Availability", back_populates="referee", lazy='dynamic')
    reviews_given = relationship("Review", back_populates="reviewer", lazy='dynamic', foreign_keys='Review.reviewer_id')
    reviews_received = relationship("Review", back_populates="referee", lazy='dynamic', foreign_keys='Review.referee_id')
    games_organized = relationship("Game", back_populates="organizer", lazy='dynamic')
    background_checks = relationship("BackgroundCheck", back_populates="user", lazy='dynamic')
    payments_made = relationship("Payment", back_populates="payer", lazy='dynamic', foreign_keys='Payment.payer_id')
    payments_received = relationship("Payment", back_populates="payee", lazy='dynamic', foreign_keys='Payment.payee_id')