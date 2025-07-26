import pytest
from app.services.payment_service import PaymentService
from app.database import drop_db, init_db, DatabaseManager
from app.models import User, Game, Assignment, Payment
from app.models.user import UserRole
from app.models.certification import Sport
from app.models.game import GameStatus
from app.models.assignment import AssignmentStatus
from app.models.payment import PaymentType, PaymentStatus
from datetime import datetime, timedelta
from unittest.mock import Mock, patch


@pytest.fixture
def setup_payment_test():
    """Set up test data for payment tests"""
    init_db()
    
    user_db = DatabaseManager(User)
    game_db = DatabaseManager(Game)
    assignment_db = DatabaseManager(Assignment)
    
    # Create users
    organizer = user_db.create(
        email='organizer@test.com',
        phone='+15551234567',
        password_hash='hashed',
        first_name='Test',
        last_name='Organizer',
        role=UserRole.ORGANIZER,
        is_active=True,
        stripe_customer_id='cus_test123'
    )
    
    referee = user_db.create(
        email='referee@test.com',
        phone='+15551234568',
        password_hash='hashed',
        first_name='Test',
        last_name='Referee',
        role=UserRole.REFEREE,
        is_active=True,
        stripe_customer_id='acct_test456'
    )
    
    # Create game
    game = game_db.create(
        organizer_id=organizer.id,
        sport=Sport.BASKETBALL,
        certification_level_required='intermediate',
        scheduled_date=datetime.utcnow() + timedelta(days=1),
        address='123 Court St',
        city='Phoenix',
        state='AZ',
        zip_code='85001',
        status=GameStatus.ASSIGNED,
        base_rate=75.0,
        surge_multiplier=1.2,
        final_rate=90.0
    )
    
    # Create assignment
    assignment = assignment_db.create(
        game_id=game.id,
        referee_id=referee.id,
        status=AssignmentStatus.COMPLETED,
        payment_amount=90.0,
        completed_at=datetime.utcnow()
    )
    
    yield {
        'organizer': organizer,
        'referee': referee,
        'game': game,
        'assignment': assignment
    }
    
    drop_db()


class TestPaymentService:
    """Test payment processing"""
    
    @patch('app.integrations.stripe_client.stripe')
    def test_charge_organizer(self, mock_stripe, setup_payment_test):
        """Test charging organizer for game"""
        payment_service = PaymentService()
        game = setup_payment_test['game']
        
        # Mock Stripe payment intent creation
        mock_stripe.PaymentIntent.create.return_value = {
            'id': 'pi_test123',
            'client_secret': 'pi_test123_secret',
            'amount': 10350  # $90 + 15% platform fee = $103.50
        }
        
        result = payment_service.charge_organizer(game.id, 90.0)
        
        assert 'payment_id' in result
        assert 'payment_intent_id' in result
        assert result['payment_intent_id'] == 'pi_test123'
        assert result['amount'] == 103.5  # With platform fee
    
    @patch('app.integrations.stripe_client.stripe')
    def test_process_referee_payment(self, mock_stripe, setup_payment_test):
        """Test processing referee payout"""
        payment_service = PaymentService()
        assignment = setup_payment_test['assignment']
        
        # Mock Stripe payout
        mock_stripe.Transfer.create.return_value = {'id': 'tr_test123'}
        mock_stripe.Payout.create.return_value = {'id': 'po_test123'}
        
        result = payment_service.process_referee_payment(assignment.id)
        
        assert 'payment_id' in result
        assert result['amount'] == 76.5  # $90 - 15% platform fee
        assert result['status'] == 'completed'
    
    def test_payment_records(self, setup_payment_test):
        """Test payment record creation"""
        payment_service = PaymentService()
        
        # Create a payment record
        payment_db = DatabaseManager(Payment)
        payment = payment_db.create(
            payer_id=setup_payment_test['organizer'].id,
            game_id=setup_payment_test['game'].id,
            amount=103.5,
            payment_type=PaymentType.GAME_PAYMENT,
            status=PaymentStatus.COMPLETED,
            stripe_payment_intent_id='pi_test123'
        )
        
        assert payment.id is not None
        assert payment.amount == 103.5
        assert payment.payment_type == PaymentType.GAME_PAYMENT
    
    def test_payment_history(self, setup_payment_test):
        """Test getting payment history"""
        payment_service = PaymentService()
        payment_db = DatabaseManager(Payment)
        
        # Create some payment records
        payment_db.create(
            payer_id=setup_payment_test['organizer'].id,
            game_id=setup_payment_test['game'].id,
            amount=103.5,
            payment_type=PaymentType.GAME_PAYMENT,
            status=PaymentStatus.COMPLETED
        )
        
        payment_db.create(
            payee_id=setup_payment_test['referee'].id,
            game_id=setup_payment_test['game'].id,
            assignment_id=setup_payment_test['assignment'].id,
            amount=76.5,
            payment_type=PaymentType.PAYOUT,
            status=PaymentStatus.COMPLETED
        )
        
        # Get organizer's history
        org_history = payment_service.get_payment_history(setup_payment_test['organizer'].id)
        assert len(org_history) == 1
        assert org_history[0]['type'] == 'game_payment'
        
        # Get referee's history
        ref_history = payment_service.get_payment_history(setup_payment_test['referee'].id)
        assert len(ref_history) == 1
        assert ref_history[0]['type'] == 'payout'
    
    @patch('app.integrations.stripe_client.stripe')
    def test_refund_processing(self, mock_stripe, setup_payment_test):
        """Test refund processing"""
        payment_service = PaymentService()
        payment_db = DatabaseManager(Payment)
        
        # Create completed payment
        payment = payment_db.create(
            payer_id=setup_payment_test['organizer'].id,
            game_id=setup_payment_test['game'].id,
            amount=103.5,
            payment_type=PaymentType.GAME_PAYMENT,
            status=PaymentStatus.COMPLETED,
            stripe_payment_intent_id='pi_test123'
        )
        
        # Mock Stripe refund
        mock_stripe.Refund.create.return_value = {'id': 'ref_test123'}
        
        result = payment_service.process_refund(payment.id, reason='Game cancelled')
        
        assert 'refund_id' in result
        assert result['amount'] == 103.5
        assert result['status'] == 'completed'
    
    def test_platform_fee_calculation(self, setup_payment_test):
        """Test platform fee calculations"""
        from config.config import Config
        
        base_amount = 100.0
        platform_fee = base_amount * Config.PLATFORM_FEE_PERCENTAGE
        total_with_fee = base_amount + platform_fee
        net_payout = base_amount - platform_fee
        
        assert platform_fee == 15.0  # 15% of $100
        assert total_with_fee == 115.0
        assert net_payout == 85.0