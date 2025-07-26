from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from app.database import DatabaseManager, get_db
from app.models import User, Game, Assignment, Certification, Availability
from app.models.assignment import AssignmentStatus
from app.models.certification import CertificationLevel
from app.services.user_service import UserService
from app.utils.distance import calculate_distance, is_within_distance
from config.config import Config
from app.utils.logger import get_logger
import json

logger = get_logger(__name__)


class MatchingService:
    """Service for automated referee-game matching"""
    
    def __init__(self):
        self.user_service = UserService()
        self.assignment_db = DatabaseManager(Assignment)
    
    def find_best_referee(self, game: Game) -> Optional[Tuple[User, float]]:
        """Find the best referee for a game using the matching algorithm"""
        try:
            # Get certified referees for the sport and level
            referees = self._get_eligible_referees(game)
            
            if not referees:
                logger.warning(f"No eligible referees found for game {game.id}")
                return None
            
            # Score and rank referees
            scored_referees = []
            for referee in referees:
                score = self._calculate_referee_score(referee, game)
                if score > 0:  # Only include referees with positive scores
                    scored_referees.append((referee, score))
            
            if not scored_referees:
                logger.warning(f"No referees passed scoring for game {game.id}")
                return None
            
            # Sort by score (highest first)
            scored_referees.sort(key=lambda x: x[1], reverse=True)
            
            # Return the best match
            best_referee, best_score = scored_referees[0]
            logger.info(f"Best match for game {game.id}: Referee {best_referee.id} with score {best_score:.2f}")
            
            return best_referee, best_score
            
        except Exception as e:
            logger.error(f"Error finding best referee: {str(e)}")
            return None
    
    def find_backup_referees(self, game: Game, primary_referee_id: int, count: int = 2) -> List[Tuple[User, float]]:
        """Find backup referees for a game"""
        try:
            # Get certified referees excluding the primary
            referees = self._get_eligible_referees(game, exclude_id=primary_referee_id)
            
            # Score and rank
            scored_referees = []
            for referee in referees:
                score = self._calculate_referee_score(referee, game)
                if score > 0:
                    scored_referees.append((referee, score))
            
            # Sort and return top backups
            scored_referees.sort(key=lambda x: x[1], reverse=True)
            return scored_referees[:count]
            
        except Exception as e:
            logger.error(f"Error finding backup referees: {str(e)}")
            return []
    
    def check_emergency_pool(self, game: Game) -> Optional[Tuple[User, float]]:
        """Check emergency pool for high-reliability referees"""
        try:
            with get_db() as db:
                # Get emergency pool referees
                query = db.query(User).filter(
                    User.role == 'referee',
                    User.is_active == True,
                    User.emergency_pool_opt_in == True,
                    User.reliability_score >= 0.9  # High reliability only
                )
                
                # Join with certifications
                query = query.join(Certification).filter(
                    Certification.sport == game.sport,
                    Certification.is_active == True
                )
                
                referees = query.all()
                
                # Score and find best from emergency pool
                best_referee = None
                best_score = 0
                
                for referee in referees:
                    if self._is_referee_available(referee, game):
                        score = self._calculate_referee_score(referee, game, is_emergency=True)
                        if score > best_score:
                            best_referee = referee
                            best_score = score
                
                if best_referee:
                    logger.info(f"Found emergency referee {best_referee.id} for game {game.id}")
                    return best_referee, best_score
                
                return None
                
        except Exception as e:
            logger.error(f"Error checking emergency pool: {str(e)}")
            return None
    
    def _get_eligible_referees(self, game: Game, exclude_id: int = None) -> List[User]:
        """Get referees eligible for a game"""
        try:
            with get_db() as db:
                # Base query for active referees
                query = db.query(User).filter(
                    User.role == 'referee',
                    User.is_active == True,
                    User.background_check_status == 'clear'
                )
                
                if exclude_id:
                    query = query.filter(User.id != exclude_id)
                
                # Join with certifications for sport and level
                query = query.join(Certification).filter(
                    Certification.sport == game.sport,
                    Certification.is_active == True
                )
                
                # Filter by certification level
                required_level = game.certification_level_required.lower()
                if required_level == 'advanced':
                    query = query.filter(Certification.level == CertificationLevel.ADVANCED)
                elif required_level == 'intermediate':
                    query = query.filter(Certification.level.in_([
                        CertificationLevel.INTERMEDIATE,
                        CertificationLevel.ADVANCED
                    ]))
                # Entry level accepts all certification levels
                
                referees = query.all()
                
                # Filter by distance
                eligible = []
                for referee in referees:
                    if referee.latitude and referee.longitude and game.latitude and game.longitude:
                        distance = calculate_distance(
                            referee.latitude, referee.longitude,
                            game.latitude, game.longitude
                        )
                        if distance <= referee.travel_distance_km:
                            referee.distance_to_game = distance
                            eligible.append(referee)
                
                # Filter by availability
                available_referees = []
                for referee in eligible:
                    if self._is_referee_available(referee, game):
                        available_referees.append(referee)
                
                return available_referees
                
        except Exception as e:
            logger.error(f"Error getting eligible referees: {str(e)}")
            return []
    
    def _is_referee_available(self, referee: User, game: Game) -> bool:
        """Check if referee is available for the game time"""
        try:
            # Get referee's availability
            with get_db() as db:
                availability = db.query(Availability).filter_by(
                    referee_id=referee.id
                ).first()
                
                if not availability:
                    return True  # No availability set means always available
                
                # Check specific time slots
                if availability.time_slots:
                    game_start = game.scheduled_date
                    game_end = game_start + timedelta(minutes=game.duration_minutes)
                    
                    for slot in availability.time_slots:
                        slot_start = datetime.fromisoformat(slot['start'])
                        slot_end = datetime.fromisoformat(slot['end'])
                        
                        # Check if game time overlaps with available slot
                        if (game_start >= slot_start and game_start < slot_end) or \
                           (game_end > slot_start and game_end <= slot_end):
                            return True
                
                # Check recurring weekly availability
                if availability.recurring_weekly:
                    day_name = game.scheduled_date.strftime('%A').lower()
                    day_slots = availability.recurring_weekly.get(day_name, [])
                    
                    game_time = game.scheduled_date.time()
                    for slot in day_slots:
                        # Parse time strings (format: "HH:MM")
                        start_time = datetime.strptime(slot['start'], '%H:%M').time()
                        end_time = datetime.strptime(slot['end'], '%H:%M').time()
                        
                        if start_time <= game_time <= end_time:
                            return True
                
                # Check blackout dates
                if availability.blackout_dates:
                    game_date = game.scheduled_date.date()
                    for blackout in availability.blackout_dates:
                        blackout_date = datetime.fromisoformat(blackout).date()
                        if game_date == blackout_date:
                            return False
                
                # Check for conflicting assignments
                existing_assignment = db.query(Assignment).filter(
                    Assignment.referee_id == referee.id,
                    Assignment.status.in_([
                        AssignmentStatus.CONFIRMED,
                        AssignmentStatus.NOTIFIED
                    ])
                ).join(Game).filter(
                    Game.scheduled_date.between(
                        game.scheduled_date - timedelta(hours=2),
                        game.scheduled_date + timedelta(hours=2)
                    )
                ).first()
                
                if existing_assignment:
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"Error checking referee availability: {str(e)}")
            return False
    
    def _calculate_referee_score(self, referee: User, game: Game, is_emergency: bool = False) -> float:
        """Calculate match score for a referee-game pair"""
        try:
            # Base scores
            reliability_score = referee.reliability_score or 1.0
            distance_score = 0
            experience_score = 0
            
            # Distance score (30% weight)
            if hasattr(referee, 'distance_to_game'):
                max_distance = referee.travel_distance_km
                distance_ratio = 1 - (referee.distance_to_game / max_distance)
                distance_score = max(0, distance_ratio)
            
            # Experience score (20% weight)
            if referee.total_games_completed > 0:
                # Normalize to 0-1 range (assuming 100 games is very experienced)
                experience_score = min(referee.total_games_completed / 100, 1.0)
            
            # Calculate weighted score
            if is_emergency:
                # For emergency pool, prioritize reliability more
                final_score = (
                    reliability_score * 0.7 +
                    distance_score * 0.2 +
                    experience_score * 0.1
                )
            else:
                # Standard weighting
                final_score = (
                    reliability_score * 0.5 +
                    distance_score * 0.3 +
                    experience_score * 0.2
                )
            
            # Apply penalties
            if referee.no_show_count > 0:
                # Severe penalty for no-shows
                penalty = referee.no_show_count * 0.2
                final_score = max(0, final_score - penalty)
            
            # Boost for perfect reliability
            if reliability_score == 1.0 and referee.total_games_completed >= 10:
                final_score *= 1.1  # 10% boost
            
            return round(final_score, 3)
            
        except Exception as e:
            logger.error(f"Error calculating referee score: {str(e)}")
            return 0
    
    def update_referee_reliability(self, referee_id: int, event_type: str):
        """Update referee reliability score based on events"""
        try:
            with get_db() as db:
                referee = db.query(User).filter_by(id=referee_id).first()
                if not referee:
                    return
                
                current_score = referee.reliability_score or 1.0
                
                if event_type == 'confirmed':
                    # Small boost for confirming
                    new_score = min(1.0, current_score + 0.01)
                elif event_type == 'completed':
                    # Boost for completing game
                    new_score = min(1.0, current_score + 0.02)
                    referee.total_games_completed += 1
                elif event_type == 'rejected':
                    # Small penalty for rejecting
                    new_score = max(0.5, current_score - 0.05)
                elif event_type == 'no_response':
                    # Penalty for not responding
                    new_score = max(0.5, current_score - 0.1)
                elif event_type == 'no_show':
                    # Severe penalty for no-show
                    new_score = max(0.3, current_score - 0.3)
                    referee.no_show_count += 1
                elif event_type == 'good_review':
                    # Boost for good review (4-5 stars)
                    new_score = min(1.0, current_score + 0.03)
                elif event_type == 'bad_review':
                    # Penalty for bad review (1-2 stars)
                    new_score = max(0.5, current_score - 0.05)
                else:
                    new_score = current_score
                
                referee.reliability_score = round(new_score, 3)
                db.commit()
                
                logger.info(f"Updated referee {referee_id} reliability: {current_score:.3f} -> {new_score:.3f}")
                
        except Exception as e:
            logger.error(f"Error updating referee reliability: {str(e)}")