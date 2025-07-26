from datetime import datetime
from typing import Dict, List, Optional
from app.database import DatabaseManager, get_db
from app.models import User, Availability, Certification
from app.utils.distance import get_coordinates_from_address
from app.utils.logger import get_logger

logger = get_logger(__name__)


class UserService:
    """Service for user management"""
    
    def __init__(self):
        self.user_db = DatabaseManager(User)
        self.availability_db = DatabaseManager(Availability)
        self.cert_db = DatabaseManager(Certification)
    
    def get_user_profile(self, user_id: int) -> Dict:
        """Get user profile data"""
        try:
            user = self.user_db.get(user_id)
            if not user:
                return {'error': 'User not found'}
            
            profile = {
                'id': user.id,
                'email': user.email,
                'phone': user.phone,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role.value,
                'address': user.address,
                'city': user.city,
                'state': user.state,
                'zip_code': user.zip_code,
                'is_active': user.is_active,
                'email_verified': user.email_verified,
                'phone_verified': user.phone_verified,
                'created_at': user.created_at.isoformat()
            }
            
            # Add role-specific fields
            if user.role.value == 'referee':
                profile.update({
                    'reliability_score': user.reliability_score,
                    'total_games_completed': user.total_games_completed,
                    'background_check_status': user.background_check_status,
                    'emergency_pool_opt_in': user.emergency_pool_opt_in,
                    'travel_distance_km': user.travel_distance_km
                })
            elif user.role.value == 'organizer':
                profile.update({
                    'organization_name': user.organization_name,
                    'organization_type': user.organization_type
                })
            
            return profile
            
        except Exception as e:
            logger.error(f"Error getting user profile: {str(e)}")
            return {'error': 'Failed to get profile'}
    
    def update_profile(self, user_id: int, data: Dict) -> Dict:
        """Update user profile"""
        try:
            # Fields that can be updated
            allowed_fields = [
                'first_name', 'last_name', 'address', 'city', 'state', 'zip_code',
                'travel_distance_km', 'notification_preferences'
            ]
            
            update_data = {k: v for k, v in data.items() if k in allowed_fields}
            
            # Update coordinates if address changed
            if any(key in update_data for key in ['address', 'city', 'state', 'zip_code']):
                user = self.user_db.get(user_id)
                coords = get_coordinates_from_address(
                    update_data.get('address', user.address),
                    update_data.get('city', user.city),
                    update_data.get('state', user.state),
                    update_data.get('zip_code', user.zip_code)
                )
                if coords:
                    update_data['latitude'], update_data['longitude'] = coords
            
            self.user_db.update(user_id, **update_data)
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error updating profile: {str(e)}")
            return {'error': 'Failed to update profile'}
    
    def get_availability(self, referee_id: int) -> Dict:
        """Get referee availability"""
        try:
            availability = self.availability_db.get_by(referee_id=referee_id)
            
            if not availability:
                return {
                    'time_slots': [],
                    'recurring_weekly': {},
                    'blackout_dates': []
                }
            
            return {
                'id': availability.id,
                'time_slots': availability.time_slots or [],
                'recurring_weekly': availability.recurring_weekly or {},
                'blackout_dates': availability.blackout_dates or [],
                'calendar_sync_enabled': availability.calendar_sync_enabled,
                'last_sync': availability.last_sync.isoformat() if availability.last_sync else None
            }
            
        except Exception as e:
            logger.error(f"Error getting availability: {str(e)}")
            return {'error': 'Failed to get availability'}
    
    def update_availability(self, referee_id: int, data: Dict) -> Dict:
        """Update referee availability"""
        try:
            availability = self.availability_db.get_by(referee_id=referee_id)
            
            if availability:
                # Update existing
                self.availability_db.update(
                    availability.id,
                    time_slots=data.get('time_slots', availability.time_slots),
                    recurring_weekly=data.get('recurring_weekly', availability.recurring_weekly),
                    blackout_dates=data.get('blackout_dates', availability.blackout_dates)
                )
            else:
                # Create new
                self.availability_db.create(
                    referee_id=referee_id,
                    time_slots=data.get('time_slots', []),
                    recurring_weekly=data.get('recurring_weekly', {}),
                    blackout_dates=data.get('blackout_dates', [])
                )
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error updating availability: {str(e)}")
            return {'error': 'Failed to update availability'}
    
    def get_certifications(self, referee_id: int) -> List[Dict]:
        """Get referee certifications"""
        try:
            certs = self.cert_db.filter(referee_id=referee_id, is_active=True)
            
            return [{
                'id': cert.id,
                'sport': cert.sport.value,
                'level': cert.level.value,
                'passed_date': cert.passed_date.isoformat() if cert.passed_date else None,
                'expiry_date': cert.expiry_date.isoformat() if cert.expiry_date else None,
                'quiz_score': cert.quiz_score,
                'is_expired': cert.expiry_date < datetime.utcnow() if cert.expiry_date else False
            } for cert in certs]
            
        except Exception as e:
            logger.error(f"Error getting certifications: {str(e)}")
            return []
    
    def update_emergency_pool(self, referee_id: int, opt_in: bool) -> Dict:
        """Update emergency pool opt-in status"""
        try:
            self.user_db.update(referee_id, emergency_pool_opt_in=opt_in)
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error updating emergency pool: {str(e)}")
            return {'error': 'Failed to update emergency pool status'}
    
    def get_referees_by_criteria(self, sport: str, level: str, location: Dict = None,
                                max_distance_km: int = None) -> List[User]:
        """Get referees matching criteria"""
        try:
            with get_db() as db:
                # Base query
                query = db.query(User).filter(
                    User.role == 'referee',
                    User.is_active == True
                )
                
                # Join with certifications
                query = query.join(Certification).filter(
                    Certification.sport == sport,
                    Certification.level == level,
                    Certification.is_active == True
                )
                
                referees = query.all()
                
                # Filter by distance if location provided
                if location and max_distance_km:
                    from app.utils.distance import calculate_distance
                    
                    filtered_referees = []
                    for ref in referees:
                        if ref.latitude and ref.longitude:
                            distance = calculate_distance(
                                ref.latitude, ref.longitude,
                                location['latitude'], location['longitude']
                            )
                            if distance <= max_distance_km:
                                ref.distance_to_game = distance
                                filtered_referees.append(ref)
                    
                    return filtered_referees
                
                return referees
                
        except Exception as e:
            logger.error(f"Error getting referees by criteria: {str(e)}")
            return []