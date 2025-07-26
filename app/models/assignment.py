from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
import enum
from .base import BaseModel


class AssignmentStatus(enum.Enum):
    PENDING = "pending"
    NOTIFIED = "notified"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class Assignment(BaseModel):
    __tablename__ = 'assignments'
    
    game_id = Column(Integer, ForeignKey('games.id'), nullable=False)
    referee_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Status
    status = Column(Enum(AssignmentStatus), default=AssignmentStatus.PENDING, index=True)
    is_backup = Column(Boolean, default=False)
    
    # Scoring
    match_score = Column(Float)  # Algorithm score when matched
    distance_km = Column(Float)
    
    # Timing
    notified_at = Column(DateTime)
    response_deadline = Column(DateTime)
    confirmed_at = Column(DateTime)
    rejected_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Payment
    payment_amount = Column(Float)
    payment_status = Column(String(50))
    
    # Relationships
    game = relationship("Game", back_populates="assignments")
    referee = relationship("User", back_populates="assignments", foreign_keys=[referee_id])
    review = relationship("Review", back_populates="assignment", uselist=False)