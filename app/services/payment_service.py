from datetime import datetime
from typing import Dict, Optional, List
from app.database import DatabaseManager, get_db
from app.models import Payment, Transaction, Assignment, Game, User
from app.models.payment import PaymentType, PaymentStatus
from app.integrations import StripeClient
from app.services.notification_service import NotificationService
from config.config import Config
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PaymentService:
    """Service for handling payments"""
    
    def __init__(self):
        self.payment_db = DatabaseManager(Payment)
        self.transaction_db = DatabaseManager(Transaction)
        self.stripe = StripeClient()
        self.notification_service = NotificationService()
    
    def charge_organizer(self, game_id: int, amount: float) -> Dict:
        """Charge organizer for game"""
        try:
            with get_db() as db:
                game = db.query(Game).filter_by(id=game_id).first()
                if not game:
                    return {'error': 'Game not found'}
                
                organizer = db.query(User).filter_by(id=game.organizer_id).first()
                if not organizer:
                    return {'error': 'Organizer not found'}
                
                # Create or get Stripe customer
                if not organizer.stripe_customer_id:
                    customer = self.stripe.create_customer(
                        organizer.email,
                        f"{organizer.first_name} {organizer.last_name}",
                        organizer.phone
                    )
                    if customer:
                        organizer.stripe_customer_id = customer['id']
                        db.commit()
                
                # Calculate total amount with platform fee
                platform_fee = amount * Config.PLATFORM_FEE_PERCENTAGE
                total_amount = amount + platform_fee
                
                # Create payment intent
                intent = self.stripe.create_payment_intent(
                    int(total_amount * 100),  # Convert to cents
                    organizer.stripe_customer_id,
                    f"Referee service for {game.sport.value} game on {game.scheduled_date.strftime('%B %d')}",
                    {
                        'game_id': str(game_id),
                        'organizer_id': str(organizer.id),
                        'platform_fee': str(platform_fee)
                    }
                )
                
                if not intent:
                    return {'error': 'Failed to create payment intent'}
                
                # Create payment record
                payment = self.payment_db.create(
                    payer_id=organizer.id,
                    game_id=game_id,
                    amount=total_amount,
                    payment_type=PaymentType.GAME_PAYMENT,
                    status=PaymentStatus.PENDING,
                    stripe_payment_intent_id=intent['id']
                )
                
                # Create transaction records
                self.transaction_db.create(
                    payment_id=payment.id,
                    transaction_type='charge',
                    amount=amount,
                    description='Referee service fee',
                    platform_fee=platform_fee,
                    net_amount=amount
                )
                
                logger.info(f"Created payment intent for game {game_id}: ${total_amount}")
                
                return {
                    'payment_id': payment.id,
                    'payment_intent_id': intent['id'],
                    'client_secret': intent['client_secret'],
                    'amount': total_amount
                }
                
        except Exception as e:
            logger.error(f"Error charging organizer: {str(e)}")
            return {'error': 'Failed to process payment'}
    
    def process_referee_payment(self, assignment_id: int) -> Dict:
        """Process payment to referee after game completion"""
        try:
            with get_db() as db:
                assignment = db.query(Assignment).filter_by(id=assignment_id).first()
                if not assignment:
                    return {'error': 'Assignment not found'}
                
                referee = db.query(User).filter_by(id=assignment.referee_id).first()
                game = db.query(Game).filter_by(id=assignment.game_id).first()
                
                if not referee or not game:
                    return {'error': 'Missing data for payment'}
                
                # Check if already paid
                existing_payment = db.query(Payment).filter_by(
                    assignment_id=assignment_id,
                    payment_type=PaymentType.PAYOUT,
                    status=PaymentStatus.COMPLETED
                ).first()
                
                if existing_payment:
                    return {'error': 'Payment already processed'}
                
                # Create Stripe connected account if needed
                if not referee.stripe_customer_id:
                    account = self.stripe.create_connected_account(referee.email)
                    if account:
                        referee.stripe_customer_id = account['id']
                        
                        # Generate onboarding link
                        return_url = f"{Config.APP_URL}/stripe/connected/return"
                        refresh_url = f"{Config.APP_URL}/stripe/connected/refresh"
                        onboarding_url = self.stripe.create_account_link(
                            account['id'], return_url, refresh_url
                        )
                        
                        if onboarding_url:
                            logger.info(f"Referee {referee.id} needs Stripe onboarding")
                            return {
                                'needs_onboarding': True,
                                'onboarding_url': onboarding_url
                            }
                
                # Calculate payout amount (after platform fee)
                gross_amount = assignment.payment_amount or game.final_rate
                platform_fee = gross_amount * Config.PLATFORM_FEE_PERCENTAGE
                net_amount = gross_amount - platform_fee
                
                # Create payout
                payout_result = self.stripe.create_payout(
                    referee.stripe_customer_id,
                    int(net_amount * 100),  # Convert to cents
                    f"Payment for {game.sport.value} game on {game.scheduled_date.strftime('%B %d')}"
                )
                
                if not payout_result:
                    return {'error': 'Failed to create payout'}
                
                # Create payment record
                payment = self.payment_db.create(
                    payee_id=referee.id,
                    game_id=game.id,
                    assignment_id=assignment.id,
                    amount=net_amount,
                    payment_type=PaymentType.PAYOUT,
                    status=PaymentStatus.COMPLETED,
                    stripe_payout_id=payout_result['payout']['id'],
                    processed_at=datetime.utcnow()
                )
                
                # Create transaction record
                self.transaction_db.create(
                    payment_id=payment.id,
                    transaction_type='payout',
                    amount=gross_amount,
                    description='Game payment to referee',
                    platform_fee=platform_fee,
                    net_amount=net_amount,
                    stripe_transaction_id=payout_result['transfer']['id']
                )
                
                # Update assignment payment status
                assignment.payment_status = 'paid'
                db.commit()
                
                # Send notification
                self.notification_service.send_payment_notification(referee.id, net_amount)
                
                logger.info(f"Processed payout for assignment {assignment_id}: ${net_amount}")
                
                return {
                    'payment_id': payment.id,
                    'amount': net_amount,
                    'status': 'completed'
                }
                
        except Exception as e:
            logger.error(f"Error processing referee payment: {str(e)}")
            return {'error': 'Failed to process payment'}
    
    def process_refund(self, payment_id: int, amount: float = None, reason: str = None) -> Dict:
        """Process refund for a payment"""
        try:
            payment = self.payment_db.get(payment_id)
            if not payment:
                return {'error': 'Payment not found'}
            
            if payment.status != PaymentStatus.COMPLETED:
                return {'error': 'Can only refund completed payments'}
            
            if not payment.stripe_payment_intent_id:
                return {'error': 'No payment intent found'}
            
            # Create refund
            refund = self.stripe.create_refund(
                payment.stripe_payment_intent_id,
                int(amount * 100) if amount else None,
                reason
            )
            
            if not refund:
                return {'error': 'Failed to create refund'}
            
            # Create refund payment record
            refund_payment = self.payment_db.create(
                payer_id=payment.payee_id,  # Reverse of original
                payee_id=payment.payer_id,
                game_id=payment.game_id,
                amount=amount or payment.amount,
                payment_type=PaymentType.REFUND,
                status=PaymentStatus.COMPLETED,
                stripe_refund_id=refund['id'],
                processed_at=datetime.utcnow()
            )
            
            # Update original payment status
            payment.status = PaymentStatus.REFUNDED
            self.payment_db.update(payment_id, status=PaymentStatus.REFUNDED)
            
            logger.info(f"Processed refund for payment {payment_id}")
            
            return {
                'refund_id': refund_payment.id,
                'amount': amount or payment.amount,
                'status': 'completed'
            }
            
        except Exception as e:
            logger.error(f"Error processing refund: {str(e)}")
            return {'error': 'Failed to process refund'}
    
    def get_payment_history(self, user_id: int) -> List[Dict]:
        """Get payment history for a user"""
        try:
            with get_db() as db:
                # Get payments where user is payer or payee
                payments = db.query(Payment).filter(
                    (Payment.payer_id == user_id) | (Payment.payee_id == user_id)
                ).order_by(Payment.created_at.desc()).all()
                
                results = []
                for payment in payments:
                    # Get related game
                    game = db.query(Game).filter_by(id=payment.game_id).first() if payment.game_id else None
                    
                    results.append({
                        'id': payment.id,
                        'date': payment.created_at.isoformat(),
                        'amount': payment.amount,
                        'type': payment.payment_type.value,
                        'status': payment.status.value,
                        'description': self._get_payment_description(payment, game, user_id),
                        'game': {
                            'sport': game.sport.value,
                            'date': game.scheduled_date.isoformat()
                        } if game else None
                    })
                
                return results
                
        except Exception as e:
            logger.error(f"Error getting payment history: {str(e)}")
            return []
    
    def _get_payment_description(self, payment: Payment, game: Optional[Game], user_id: int) -> str:
        """Generate payment description"""
        if payment.payment_type == PaymentType.GAME_PAYMENT:
            if payment.payer_id == user_id:
                return f"Referee service for {game.sport.value if game else 'game'}"
            else:
                return f"Platform fee received"
        elif payment.payment_type == PaymentType.PAYOUT:
            return f"Payment for {game.sport.value if game else 'game'} officiating"
        elif payment.payment_type == PaymentType.REFUND:
            return "Refund"
        else:
            return "Payment"