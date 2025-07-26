from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime, JSON, Enum
from sqlalchemy.orm import relationship
import enum
from datetime import datetime, timedelta
from .base import BaseModel


class CertificationLevel(enum.Enum):
    ENTRY = "entry"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Sport(enum.Enum):
    BASKETBALL = "basketball"
    FOOTBALL = "football"
    SOCCER = "soccer"
    SOFTBALL = "softball"
    VOLLEYBALL = "volleyball"
    BASEBALL = "baseball"


class Certification(BaseModel):
    __tablename__ = 'certifications'
    
    referee_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    sport = Column(Enum(Sport), nullable=False)
    level = Column(Enum(CertificationLevel), nullable=False)
    is_active = Column(Boolean, default=True)
    passed_date = Column(DateTime)
    expiry_date = Column(DateTime)
    quiz_score = Column(Float)
    
    # Relationships
    referee = relationship("User", back_populates="certifications")
    quiz_attempts = relationship("QuizAttempt", back_populates="certification", lazy='dynamic')


class QuizQuestion(BaseModel):
    __tablename__ = 'quiz_questions'
    
    sport = Column(Enum(Sport), nullable=False)
    level = Column(Enum(CertificationLevel), nullable=False)
    question = Column(String(1000), nullable=False)
    options = Column(JSON, nullable=False)  # List of options
    correct_answer = Column(Integer, nullable=False)  # Index of correct option
    explanation = Column(String(500))
    is_active = Column(Boolean, default=True)


class QuizAttempt(BaseModel):
    __tablename__ = 'quiz_attempts'
    
    referee_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    certification_id = Column(Integer, ForeignKey('certifications.id'))
    sport = Column(Enum(Sport), nullable=False)
    level = Column(Enum(CertificationLevel), nullable=False)
    questions = Column(JSON)  # List of question IDs
    answers = Column(JSON)  # User's answers
    score = Column(Float)
    passed = Column(Boolean, default=False)
    completed_at = Column(DateTime)
    
    # Relationships
    certification = relationship("Certification", back_populates="quiz_attempts")