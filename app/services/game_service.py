from datetime import datetime, timedelta
from typing import Dict, List, Optional
from app.database import DatabaseManager, get_db
from app.models import Game, User, Assignment
from app.models.game import GameStatus
from app.models.certification import Sport
from app.utils.distance import get_coordinates_from_address
from config.config import Config
from app.utils.logger import get_logger
import re

logger = get_logger(__name__)


class GameService:
    """Service for game management"""
    
    def __init__(self):
        self.game_db = DatabaseManager(Game)
        self.user_db = DatabaseManager(User)
    
    def create_game(self, game_data: Dict) -> Dict:
        """Create a new game"""
        try:
            # Convert sport string to enum
            sport_map = {
                'basketball': Sport.BASKETBALL,
                'football': Sport.FOOTBALL,
                'soccer': Sport.SOCCER,
                'softball': Sport.SOFTBALL,
                'volleyball': Sport.VOLLEYBALL,
                'baseball': Sport.BASEBALL
            }
            game_data['sport'] = sport_map.get(game_data['sport'].lower())
            
            if not game_data['sport']:
                return {'error': 'Invalid sport'}
            
            # Get coordinates for game location
            coords = get_coordinates_from_address(
                game_data['address'],
                game_data['city'],
                game_data['state'],
                game_data['zip_code']
            )
            if coords:
                game_data['latitude'], game_data['longitude'] = coords
            
            # Set base rate based on sport and level
            base_rates = Config.BASE_RATES.get(game_data['sport'].value, {})
            game_data['base_rate'] = base_rates.get(
                game_data['certification_level_required'], 50
            )
            
            # Calculate initial surge pricing
            surge_multiplier = self._calculate_surge_multiplier(
                game_data.get('scheduled_date'),
                game_data.get('importance', 3)
            )
            game_data['surge_multiplier'] = surge_multiplier
            game_data['final_rate'] = game_data['base_rate'] * surge_multiplier
            
            # Create game
            game = self.game_db.create(**game_data)
            
            logger.info(f"Game created: {game.id} for {game.sport.value} on {game.scheduled_date}")
            
            return {'game_id': game.id, 'success': True}
            
        except Exception as e:
            logger.error(f"Error creating game: {str(e)}")
            return {'error': 'Failed to create game'}
    
    def get_game_details(self, game_id: int) -> Dict:
        """Get detailed game information"""
        try:
            game = self.game_db.get(game_id)
            if not game:
                return {'error': 'Game not found'}
            
            return self._format_game(game)
            
        except Exception as e:
            logger.error(f"Error getting game details: {str(e)}")
            return {'error': 'Failed to get game details'}
    
    def update_game(self, game_id: int, updates: Dict) -> Dict:
        """Update game details"""
        try:
            # Fields that can be updated
            allowed_fields = [
                'scheduled_date', 'venue_name', 'address', 'city', 'state',
                'zip_code', 'home_team', 'away_team', 'importance', 'notes'
            ]
            
            update_data = {k: v for k, v in updates.items() if k in allowed_fields}
            
            # Update coordinates if location changed
            if any(key in update_data for key in ['address', 'city', 'state', 'zip_code']):
                game = self.game_db.get(game_id)
                coords = get_coordinates_from_address(
                    update_data.get('address', game.address),
                    update_data.get('city', game.city),
                    update_data.get('state', game.state),
                    update_data.get('zip_code', game.zip_code)
                )
                if coords:
                    update_data['latitude'], update_data['longitude'] = coords
            
            # Recalculate surge pricing if date or importance changed
            if 'scheduled_date' in update_data or 'importance' in update_data:
                game = self.game_db.get(game_id)
                surge_multiplier = self._calculate_surge_multiplier(
                    update_data.get('scheduled_date', game.scheduled_date),
                    update_data.get('importance', game.importance)
                )
                update_data['surge_multiplier'] = surge_multiplier
                update_data['final_rate'] = game.base_rate * surge_multiplier
            
            self.game_db.update(game_id, **update_data)
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error updating game: {str(e)}")
            return {'error': 'Failed to update game'}
    
    def cancel_game(self, game_id: int) -> Dict:
        """Cancel a game"""
        try:
            game = self.game_db.get(game_id)
            if not game:
                return {'error': 'Game not found'}
            
            if game.status != GameStatus.PENDING:
                return {'error': 'Can only cancel pending games'}
            
            self.game_db.update(game_id, status=GameStatus.CANCELLED)
            
            # TODO: Notify assigned referee if any
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error cancelling game: {str(e)}")
            return {'error': 'Failed to cancel game'}
    
    def get_organizer_games(self, organizer_id: int, status: str = None,
                           start_date: datetime = None, end_date: datetime = None) -> List[Dict]:
        """Get games for an organizer"""
        try:
            with get_db() as db:
                query = db.query(Game).filter(Game.organizer_id == organizer_id)
                
                if status:
                    query = query.filter(Game.status == GameStatus[status.upper()])
                
                if start_date:
                    query = query.filter(Game.scheduled_date >= start_date)
                
                if end_date:
                    query = query.filter(Game.scheduled_date <= end_date)
                
                games = query.order_by(Game.scheduled_date.desc()).all()
                
                return [self._format_game(game) for game in games]
                
        except Exception as e:
            logger.error(f"Error getting organizer games: {str(e)}")
            return []
    
    def get_referee_games(self, referee_id: int, status: str = None,
                         start_date: datetime = None, end_date: datetime = None) -> List[Dict]:
        """Get games assigned to a referee"""
        try:
            with get_db() as db:
                query = db.query(Game).join(Assignment).filter(
                    Assignment.referee_id == referee_id
                )
                
                if status:
                    query = query.filter(Game.status == GameStatus[status.upper()])
                
                if start_date:
                    query = query.filter(Game.scheduled_date >= start_date)
                
                if end_date:
                    query = query.filter(Game.scheduled_date <= end_date)
                
                games = query.order_by(Game.scheduled_date.desc()).all()
                
                return [self._format_game(game) for game in games]
                
        except Exception as e:
            logger.error(f"Error getting referee games: {str(e)}")
            return []
    
    def get_all_games(self, status: str = None, start_date: datetime = None,
                     end_date: datetime = None) -> List[Dict]:
        """Get all games (admin)"""
        try:
            with get_db() as db:
                query = db.query(Game)
                
                if status:
                    query = query.filter(Game.status == GameStatus[status.upper()])
                
                if start_date:
                    query = query.filter(Game.scheduled_date >= start_date)
                
                if end_date:
                    query = query.filter(Game.scheduled_date <= end_date)
                
                games = query.order_by(Game.scheduled_date.desc()).all()
                
                return [self._format_game(game) for game in games]
                
        except Exception as e:
            logger.error(f"Error getting all games: {str(e)}")
            return []
    
    def get_pending_games_for_assignment(self) -> List[Game]:
        """Get pending games that need referee assignment"""
        try:
            with get_db() as db:
                # Get games that are pending and scheduled for the future
                games = db.query(Game).filter(
                    Game.status == GameStatus.PENDING,
                    Game.scheduled_date > datetime.utcnow()
                ).order_by(Game.scheduled_date).all()
                
                return games
                
        except Exception as e:
            logger.error(f"Error getting pending games: {str(e)}")
            return []
    
    def parse_email_submission(self, email_content: str, from_email: str) -> Dict:
        """Parse game details from email content"""
        try:
            # Find organizer by email
            organizer = self.user_db.get_by(email=from_email)
            if not organizer or organizer.role.value != 'organizer':
                return {'error': 'Email not from registered organizer'}
            
            # Simple email parsing (in production, use more sophisticated parsing)
            parsed = {
                'organizer_id': organizer.id
            }
            
            # Extract sport
            sport_match = re.search(r'sport:\s*(\w+)', email_content, re.IGNORECASE)
            if sport_match:
                parsed['sport'] = sport_match.group(1).lower()
            
            # Extract date
            date_match = re.search(r'date:\s*([\d\-\s:]+)', email_content, re.IGNORECASE)
            if date_match:
                parsed['scheduled_date'] = date_match.group(1)
            
            # Extract location
            location_match = re.search(r'location:\s*(.+)', email_content, re.IGNORECASE)
            if location_match:
                # Parse address components
                location = location_match.group(1)
                # This is simplified - in production, use proper address parsing
                parts = location.split(',')
                if len(parts) >= 3:
                    parsed['address'] = parts[0].strip()
                    parsed['city'] = parts[1].strip()
                    state_zip = parts[2].strip().split()
                    if len(state_zip) >= 2:
                        parsed['state'] = state_zip[0]
                        parsed['zip_code'] = state_zip[1]
            
            # Extract teams
            home_match = re.search(r'home:\s*(.+)', email_content, re.IGNORECASE)
            if home_match:
                parsed['home_team'] = home_match.group(1).strip()
            
            away_match = re.search(r'away:\s*(.+)', email_content, re.IGNORECASE)
            if away_match:
                parsed['away_team'] = away_match.group(1).strip()
            
            # Set defaults
            parsed['certification_level_required'] = 'entry'
            parsed['importance'] = 3
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing email submission: {str(e)}")
            return {'error': 'Failed to parse email'}
    
    def _calculate_surge_multiplier(self, scheduled_date: datetime, importance: int) -> float:
        """Calculate surge pricing multiplier"""
        # Base multiplier
        multiplier = 1.0
        
        # Time-based surge (less than 24 hours notice)
        if scheduled_date:
            hours_until_game = (scheduled_date - datetime.utcnow()).total_seconds() / 3600
            if hours_until_game < 24:
                multiplier += 0.2  # 20% surge for last-minute games
        
        # Importance-based surge
        if importance:
            multiplier += (importance - 3) * 0.05  # 5% per importance level above 3
        
        # Demand-based surge (simplified - count pending games)
        pending_count = self.game_db.count(status=GameStatus.PENDING)
        demand_factor = min(pending_count / 10, 0.3)  # Max 30% for high demand
        multiplier += demand_factor
        
        # Cap at configured maximum
        return min(multiplier, Config.SURGE_PRICING_CAP)
    
    def _format_game(self, game: Game) -> Dict:
        """Format game object for API response"""
        return {
            'id': game.id,
            'organizer_id': game.organizer_id,
            'sport': game.sport.value,
            'certification_level_required': game.certification_level_required,
            'scheduled_date': game.scheduled_date.isoformat(),
            'duration_minutes': game.duration_minutes,
            'venue_name': game.venue_name,
            'address': game.address,
            'city': game.city,
            'state': game.state,
            'zip_code': game.zip_code,
            'latitude': game.latitude,
            'longitude': game.longitude,
            'home_team': game.home_team,
            'away_team': game.away_team,
            'importance': game.importance,
            'notes': game.notes,
            'status': game.status.value,
            'base_rate': game.base_rate,
            'surge_multiplier': game.surge_multiplier,
            'final_rate': game.final_rate,
            'created_at': game.created_at.isoformat()
        }