import pytest
from datetime import datetime, timedelta
from app.services.matching_service import MatchingService
from app.database import drop_db, init_db, DatabaseManager
from app.models import User, Game, Certification, Availability
from app.models.user import UserRole
from app.models.certification import Sport, CertificationLevel
from app.models.game import GameStatus


@pytest.fixture
def setup_test_data():
    """Set up test database with sample data"""
    init_db()
    
    user_db = DatabaseManager(User)
    game_db = DatabaseManager(Game)
    cert_db = DatabaseManager(Certification)
    avail_db = DatabaseManager(Availability)
    
    # Create organizer
    organizer = user_db.create(
        email='organizer@test.com',
        phone='+15551234567',
        password_hash='hashed',
        first_name='Test',
        last_name='Organizer',
        role=UserRole.ORGANIZER,
        is_active=True,
        organization_name='Test School'
    )
    
    # Create referees with different attributes
    referee1 = user_db.create(
        email='ref1@test.com',
        phone='+15551234568',
        password_hash='hashed',
        first_name='Ref',
        last_name='One',
        role=UserRole.REFEREE,
        is_active=True,
        background_check_status='clear',
        reliability_score=0.95,
        total_games_completed=20,
        latitude=33.4484,  # Phoenix area
        longitude=-112.0740,
        travel_distance_km=30
    )
    
    referee2 = user_db.create(
        email='ref2@test.com',
        phone='+15551234569',
        password_hash='hashed',
        first_name='Ref',
        last_name='Two',
        role=UserRole.REFEREE,
        is_active=True,
        background_check_status='clear',
        reliability_score=0.85,
        total_games_completed=10,
        latitude=33.5000,  # Slightly north
        longitude=-112.1000,
        travel_distance_km=25
    )
    
    referee3 = user_db.create(
        email='ref3@test.com',
        phone='+15551234570',
        password_hash='hashed',
        first_name='Ref',
        last_name='Three',
        role=UserRole.REFEREE,
        is_active=True,
        background_check_status='clear',
        reliability_score=0.90,
        total_games_completed=5,
        latitude=33.4000,  # South Phoenix
        longitude=-112.0500,
        travel_distance_km=40,
        emergency_pool_opt_in=True
    )
    
    # Create certifications
    cert_db.create(
        referee_id=referee1.id,
        sport=Sport.BASKETBALL,
        level=CertificationLevel.ADVANCED,
        is_active=True,
        passed_date=datetime.utcnow() - timedelta(days=30)
    )
    
    cert_db.create(
        referee_id=referee2.id,
        sport=Sport.BASKETBALL,
        level=CertificationLevel.INTERMEDIATE,
        is_active=True,
        passed_date=datetime.utcnow() - timedelta(days=60)
    )
    
    cert_db.create(
        referee_id=referee3.id,
        sport=Sport.BASKETBALL,
        level=CertificationLevel.ADVANCED,
        is_active=True,
        passed_date=datetime.utcnow() - timedelta(days=90)
    )
    
    # Create availability
    tomorrow = datetime.utcnow() + timedelta(days=1)
    avail_db.create(
        referee_id=referee1.id,
        time_slots=[{
            'start': tomorrow.replace(hour=8).isoformat(),
            'end': tomorrow.replace(hour=20).isoformat()
        }]
    )
    
    avail_db.create(
        referee_id=referee2.id,
        time_slots=[{
            'start': tomorrow.replace(hour=10).isoformat(),
            'end': tomorrow.replace(hour=18).isoformat()
        }]
    )
    
    # Create a game
    game = game_db.create(
        organizer_id=organizer.id,
        sport=Sport.BASKETBALL,
        certification_level_required='intermediate',
        scheduled_date=tomorrow.replace(hour=14),
        address='456 Game St',
        city='Phoenix',
        state='AZ',
        zip_code='85002',
        latitude=33.4500,
        longitude=-112.0700,
        home_team='Home School',
        away_team='Away School',
        importance=3,
        status=GameStatus.PENDING,
        base_rate=75.0,
        surge_multiplier=1.0,
        final_rate=75.0
    )
    
    yield {
        'organizer': organizer,
        'referees': [referee1, referee2, referee3],
        'game': game
    }
    
    drop_db()


class TestMatchingService:
    """Test matching algorithm"""
    
    def test_find_best_referee(self, setup_test_data):
        """Test finding best referee for a game"""
        matching_service = MatchingService()
        game = setup_test_data['game']
        
        result = matching_service.find_best_referee(game)
        assert result is not None
        
        referee, score = result
        # Referee 1 should be best (highest reliability + advanced cert)
        assert referee.email == 'ref1@test.com'
        assert score > 0
    
    def test_distance_filtering(self, setup_test_data):
        """Test distance-based filtering"""
        matching_service = MatchingService()
        game = setup_test_data['game']
        
        # Move game far away
        game.latitude = 34.0  # Far north
        game.longitude = -113.0  # Far west
        
        from app.database import DatabaseManager
        from app.models import Game
        game_db = DatabaseManager(Game)
        game_db.update(game.id, latitude=34.0, longitude=-113.0)
        
        result = matching_service.find_best_referee(game)
        # May return None if all referees are too far
        if result:
            referee, score = result
            assert referee.travel_distance_km >= 40  # Only ref3 has 40km range
    
    def test_certification_level_filtering(self, setup_test_data):
        """Test certification level requirements"""
        matching_service = MatchingService()
        game = setup_test_data['game']
        
        # Change to advanced requirement
        from app.database import DatabaseManager
        from app.models import Game
        game_db = DatabaseManager(Game)
        game_db.update(game.id, certification_level_required='advanced')
        
        # Get eligible referees
        referees = matching_service._get_eligible_referees(game)
        
        # Only ref1 and ref3 have advanced certification
        assert len(referees) == 2
        emails = [r.email for r in referees]
        assert 'ref1@test.com' in emails
        assert 'ref3@test.com' in emails
        assert 'ref2@test.com' not in emails
    
    def test_availability_checking(self, setup_test_data):
        """Test referee availability checking"""
        matching_service = MatchingService()
        game = setup_test_data['game']
        referee1 = setup_test_data['referees'][0]
        
        # Check during available time
        is_available = matching_service._is_referee_available(referee1, game)
        assert is_available is True
        
        # Change game to early morning (outside availability)
        game.scheduled_date = game.scheduled_date.replace(hour=6)
        is_available = matching_service._is_referee_available(referee1, game)
        assert is_available is False
    
    def test_score_calculation(self, setup_test_data):
        """Test referee scoring algorithm"""
        matching_service = MatchingService()
        game = setup_test_data['game']
        
        # Calculate scores for all referees
        scores = []
        for referee in setup_test_data['referees']:
            # Calculate distance
            from app.utils.distance import calculate_distance
            distance = calculate_distance(
                referee.latitude, referee.longitude,
                game.latitude, game.longitude
            )
            referee.distance_to_game = distance
            
            score = matching_service._calculate_referee_score(referee, game)
            scores.append((referee.email, score))
        
        # Sort by score
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # Verify scoring makes sense
        assert scores[0][1] > scores[-1][1]  # Best score > worst score
    
    def test_emergency_pool(self, setup_test_data):
        """Test emergency pool functionality"""
        matching_service = MatchingService()
        game = setup_test_data['game']
        
        result = matching_service.check_emergency_pool(game)
        assert result is not None
        
        referee, score = result
        # Only ref3 is in emergency pool
        assert referee.email == 'ref3@test.com'
        assert referee.emergency_pool_opt_in is True
    
    def test_backup_referees(self, setup_test_data):
        """Test finding backup referees"""
        matching_service = MatchingService()
        game = setup_test_data['game']
        referee1 = setup_test_data['referees'][0]
        
        backups = matching_service.find_backup_referees(game, referee1.id, count=2)
        
        assert len(backups) <= 2
        # Backups should not include primary referee
        for backup_ref, score in backups:
            assert backup_ref.id != referee1.id
    
    def test_reliability_updates(self, setup_test_data):
        """Test reliability score updates"""
        matching_service = MatchingService()
        referee = setup_test_data['referees'][0]
        
        initial_score = referee.reliability_score
        
        # Test different events
        matching_service.update_referee_reliability(referee.id, 'confirmed')
        
        from app.database import DatabaseManager
        from app.models import User
        user_db = DatabaseManager(User)
        updated_ref = user_db.get(referee.id)
        
        assert updated_ref.reliability_score > initial_score
        
        # Test no-show penalty
        matching_service.update_referee_reliability(referee.id, 'no_show')
        updated_ref = user_db.get(referee.id)
        
        assert updated_ref.reliability_score < initial_score