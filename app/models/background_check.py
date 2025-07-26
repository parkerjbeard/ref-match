from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from .base import BaseModel


class BackgroundCheck(BaseModel):
    __tablename__ = 'background_checks'
    
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Checkr details
    checkr_invitation_id = Column(String(255))
    checkr_report_id = Column(String(255))
    checkr_candidate_id = Column(String(255))
    
    # Status
    status = Column(String(50), default='pending')  # pending, clear, consider, suspended
    
    # Dates
    initiated_at = Column(DateTime)
    completed_at = Column(DateTime)
    expires_at = Column(DateTime)
    
    # Results
    report_data = Column(JSON)  # Store full report data
    criminal_records = Column(JSON)
    motor_vehicle_report = Column(JSON)
    
    # Relationships
    user = relationship("User", back_populates="background_checks")