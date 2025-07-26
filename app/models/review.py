from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from .base import BaseModel


class Review(BaseModel):
    __tablename__ = 'reviews'
    
    assignment_id = Column(Integer, ForeignKey('assignments.id'), nullable=False)
    referee_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    reviewer_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    rating = Column(Integer, nullable=False)  # 1-5 scale
    comment = Column(String(1000))
    
    # Review metadata
    review_sent_at = Column(DateTime)
    review_completed_at = Column(DateTime)
    reminder_count = Column(Integer, default=0)
    
    # Relationships
    assignment = relationship("Assignment", back_populates="review")
    referee = relationship("User", back_populates="reviews_received", foreign_keys=[referee_id])
    reviewer = relationship("User", back_populates="reviews_given", foreign_keys=[reviewer_id])