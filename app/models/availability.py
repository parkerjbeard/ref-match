from sqlalchemy import Column, Integer, ForeignKey, DateTime, JSON, Boolean
from sqlalchemy.orm import relationship
from .base import BaseModel


class Availability(BaseModel):
    __tablename__ = 'availabilities'
    
    referee_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Time slots stored as JSON
    # Format: [{"start": "2024-01-15T09:00:00", "end": "2024-01-15T17:00:00"}, ...]
    time_slots = Column(JSON, nullable=False)
    
    # Recurring availability
    recurring_weekly = Column(JSON)  # e.g., {"monday": [{"start": "09:00", "end": "17:00"}], ...}
    
    # Blackout dates
    blackout_dates = Column(JSON)  # List of dates when unavailable
    
    # Calendar sync
    google_calendar_id = Column(JSON)
    calendar_sync_enabled = Column(Boolean, default=False)
    last_sync = Column(DateTime)
    
    # Relationships
    referee = relationship("User", back_populates="availabilities")