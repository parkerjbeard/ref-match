from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
import enum
from .base import BaseModel
from .certification import Sport


class GameStatus(enum.Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Game(BaseModel):
    __tablename__ = 'games'
    
    # Basic Info
    organizer_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    sport = Column(Enum(Sport), nullable=False)
    certification_level_required = Column(String(50), nullable=False)
    
    # Schedule
    scheduled_date = Column(DateTime, nullable=False, index=True)
    duration_minutes = Column(Integer, default=90)
    
    # Location
    venue_name = Column(String(255))
    address = Column(String(500), nullable=False)
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Game Details
    home_team = Column(String(255))
    away_team = Column(String(255))
    importance = Column(Integer, default=3)  # 1-5 scale
    notes = Column(String(1000))
    
    # Status
    status = Column(Enum(GameStatus), default=GameStatus.PENDING, index=True)
    
    # Pricing
    base_rate = Column(Float)
    surge_multiplier = Column(Float, default=1.0)
    final_rate = Column(Float)
    
    # Relationships
    organizer = relationship("User", back_populates="games_organized")
    assignments = relationship("Assignment", back_populates="game", lazy='dynamic')