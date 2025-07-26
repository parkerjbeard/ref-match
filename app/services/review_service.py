from datetime import datetime, timedelta
from typing import Dict, List, Optional
from app.database import DatabaseManager, get_db
from app.models import Review, Assignment, Game, User
from app.services.notification_service import NotificationService
from app.services.matching_service import MatchingService
from config.config import Config
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ReviewService:
    """Service for managing reviews"""
    
    def __init__(self):
        self.review_db = DatabaseManager(Review)
        self.notification_service = NotificationService()
        self.matching_service = MatchingService()
    
    def send_review_request(self, assignment_id: int) -> Dict:
        """Send review request after game completion"""
        try:
            with get_db() as db:
                # Get assignment and related data
                assignment = db.query(Assignment).filter_by(id=assignment_id).first()
                if not assignment:
                    return {'error': 'Assignment not found'}
                
                game = db.query(Game).filter_by(id=assignment.game_id).first()
                if not game:
                    return {'error': 'Game not found'}
                
                # Find coaches for the teams
                # For MVP, we'll use the organizer as the reviewer
                reviewer_id = game.organizer_id
                
                # Check if review already exists
                existing = db.query(Review).filter_by(
                    assignment_id=assignment_id
                ).first()
                
                if existing:
                    return {'error': 'Review already requested'}
                
                # Create review record
                review = self.review_db.create(
                    assignment_id=assignment_id,
                    referee_id=assignment.referee_id,
                    reviewer_id=reviewer_id,
                    review_sent_at=datetime.utcnow()
                )
                
                # Send notification
                self.notification_service.send_review_request(review.id)
                
                logger.info(f"Sent review request for assignment {assignment_id}")
                
                return {'review_id': review.id, 'success': True}
                
        except Exception as e:
            logger.error(f"Error sending review request: {str(e)}")
            return {'error': 'Failed to send review request'}
    
    def submit_review(self, review_id: int, rating: int, comment: str = None) -> Dict:
        """Submit a review"""
        try:
            review = self.review_db.get(review_id)
            if not review:
                return {'error': 'Review not found'}
            
            if review.rating:
                return {'error': 'Review already submitted'}
            
            # Validate rating
            if rating < 1 or rating > 5:
                return {'error': 'Rating must be between 1 and 5'}
            
            # Update review
            self.review_db.update(
                review_id,
                rating=rating,
                comment=comment,
                review_completed_at=datetime.utcnow()
            )
            
            # Update referee reliability based on rating
            if rating >= 4:
                self.matching_service.update_referee_reliability(
                    review.referee_id, 'good_review'
                )
            elif rating <= 2:
                self.matching_service.update_referee_reliability(
                    review.referee_id, 'bad_review'
                )
            
            # Update referee's average rating
            self._update_referee_average_rating(review.referee_id)
            
            logger.info(f"Review {review_id} submitted with rating {rating}")
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error submitting review: {str(e)}")
            return {'error': 'Failed to submit review'}
    
    def get_review(self, review_id: int) -> Dict:
        """Get review details"""
        try:
            with get_db() as db:
                review = db.query(Review).filter_by(id=review_id).first()
                if not review:
                    return {'error': 'Review not found'}
                
                # Get related data
                assignment = db.query(Assignment).filter_by(id=review.assignment_id).first()
                game = db.query(Game).filter_by(id=assignment.game_id).first()
                referee = db.query(User).filter_by(id=review.referee_id).first()
                reviewer = db.query(User).filter_by(id=review.reviewer_id).first()
                
                return {
                    'id': review.id,
                    'rating': review.rating,
                    'comment': review.comment,
                    'submitted': review.review_completed_at is not None,
                    'submitted_at': review.review_completed_at.isoformat() if review.review_completed_at else None,
                    'referee': {
                        'id': referee.id,
                        'name': f"{referee.first_name} {referee.last_name}"
                    },
                    'reviewer': {
                        'id': reviewer.id,
                        'name': f"{reviewer.first_name} {reviewer.last_name}"
                    },
                    'game': {
                        'id': game.id,
                        'sport': game.sport.value,
                        'date': game.scheduled_date.isoformat(),
                        'teams': f"{game.home_team} vs {game.away_team}"
                    }
                }
                
        except Exception as e:
            logger.error(f"Error getting review: {str(e)}")
            return {'error': 'Failed to get review'}
    
    def get_referee_reviews(self, referee_id: int) -> List[Dict]:
        """Get all reviews for a referee"""
        try:
            reviews = self.review_db.filter(
                referee_id=referee_id,
                rating__ne=None  # Only completed reviews
            )
            
            results = []
            for review in reviews:
                results.append({
                    'id': review.id,
                    'rating': review.rating,
                    'comment': review.comment,
                    'date': review.review_completed_at.isoformat() if review.review_completed_at else None
                })
            
            # Calculate summary stats
            if results:
                ratings = [r['rating'] for r in results]
                summary = {
                    'total_reviews': len(ratings),
                    'average_rating': sum(ratings) / len(ratings),
                    'rating_distribution': {
                        i: ratings.count(i) for i in range(1, 6)
                    }
                }
            else:
                summary = {
                    'total_reviews': 0,
                    'average_rating': 0,
                    'rating_distribution': {i: 0 for i in range(1, 6)}
                }
            
            return {
                'reviews': results,
                'summary': summary
            }
            
        except Exception as e:
            logger.error(f"Error getting referee reviews: {str(e)}")
            return {'reviews': [], 'summary': {}}
    
    def send_review_reminders(self):
        """Send reminders for pending reviews"""
        try:
            with get_db() as db:
                # Find reviews that need reminders
                cutoff_time = datetime.utcnow() - timedelta(days=3)
                
                pending_reviews = db.query(Review).filter(
                    Review.rating == None,
                    Review.review_sent_at < cutoff_time,
                    Review.reminder_count < 2  # Max 2 reminders
                ).all()
                
                for review in pending_reviews:
                    # Send reminder
                    self.notification_service.send_review_request(review.id)
                    
                    # Update reminder count
                    review.reminder_count += 1
                    db.commit()
                    
                    logger.info(f"Sent review reminder {review.reminder_count} for review {review.id}")
                    
        except Exception as e:
            logger.error(f"Error sending review reminders: {str(e)}")
    
    def _update_referee_average_rating(self, referee_id: int):
        """Update referee's average rating"""
        try:
            with get_db() as db:
                # Get all completed reviews
                reviews = db.query(Review).filter(
                    Review.referee_id == referee_id,
                    Review.rating != None
                ).all()
                
                if reviews:
                    total_rating = sum(r.rating for r in reviews)
                    avg_rating = total_rating / len(reviews)
                    
                    # Store in user's reliability score (simplified for MVP)
                    # In production, might want a separate field
                    referee = db.query(User).filter_by(id=referee_id).first()
                    if referee:
                        # Blend with existing reliability score
                        new_reliability = (referee.reliability_score * 0.7) + (avg_rating / 5 * 0.3)
                        referee.reliability_score = round(new_reliability, 3)
                        db.commit()
                        
        except Exception as e:
            logger.error(f"Error updating referee average rating: {str(e)}")