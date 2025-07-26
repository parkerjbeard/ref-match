import stripe
from typing import Dict, Optional
from config.config import Config
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Configure Stripe
stripe.api_key = Config.STRIPE_SECRET_KEY


class StripeClient:
    """Wrapper for Stripe API operations"""
    
    def __init__(self):
        self.api_key = Config.STRIPE_SECRET_KEY
        if not self.api_key:
            logger.warning("Stripe API key not configured")
    
    def create_customer(self, email: str, name: str, phone: str = None) -> Optional[Dict]:
        """Create a Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                phone=phone,
                metadata={"platform": "refmatch"}
            )
            return customer
        except stripe.error.StripeError as e:
            logger.error(f"Error creating Stripe customer: {str(e)}")
            return None
    
    def create_payment_intent(self, amount_cents: int, customer_id: str, 
                            description: str, metadata: Dict = None) -> Optional[Dict]:
        """Create a payment intent for charging organizers"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency='usd',
                customer=customer_id,
                description=description,
                metadata=metadata or {},
                automatic_payment_methods={"enabled": True}
            )
            return intent
        except stripe.error.StripeError as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            return None
    
    def confirm_payment_intent(self, payment_intent_id: str) -> Optional[Dict]:
        """Confirm a payment intent"""
        try:
            intent = stripe.PaymentIntent.confirm(payment_intent_id)
            return intent
        except stripe.error.StripeError as e:
            logger.error(f"Error confirming payment intent: {str(e)}")
            return None
    
    def create_connected_account(self, email: str, country: str = 'US') -> Optional[Dict]:
        """Create a connected account for referee payouts"""
        try:
            account = stripe.Account.create(
                type='express',
                country=country,
                email=email,
                capabilities={
                    'transfers': {'requested': True},
                },
                business_type='individual',
            )
            return account
        except stripe.error.StripeError as e:
            logger.error(f"Error creating connected account: {str(e)}")
            return None
    
    def create_account_link(self, account_id: str, return_url: str, refresh_url: str) -> Optional[str]:
        """Create account link for onboarding"""
        try:
            link = stripe.AccountLink.create(
                account=account_id,
                refresh_url=refresh_url,
                return_url=return_url,
                type='account_onboarding',
            )
            return link.url
        except stripe.error.StripeError as e:
            logger.error(f"Error creating account link: {str(e)}")
            return None
    
    def create_payout(self, account_id: str, amount_cents: int, description: str = None) -> Optional[Dict]:
        """Create instant payout to referee"""
        try:
            # First, create a transfer to the connected account
            transfer = stripe.Transfer.create(
                amount=amount_cents,
                currency='usd',
                destination=account_id,
                description=description or "Referee game payment"
            )
            
            # Then create instant payout
            payout = stripe.Payout.create(
                amount=amount_cents,
                currency='usd',
                method='instant',
                stripe_account=account_id
            )
            
            return {"transfer": transfer, "payout": payout}
        except stripe.error.StripeError as e:
            logger.error(f"Error creating payout: {str(e)}")
            return None
    
    def create_refund(self, payment_intent_id: str, amount_cents: int = None, reason: str = None) -> Optional[Dict]:
        """Create a refund"""
        try:
            refund_data = {"payment_intent": payment_intent_id}
            if amount_cents:
                refund_data["amount"] = amount_cents
            if reason:
                refund_data["reason"] = reason
                
            refund = stripe.Refund.create(**refund_data)
            return refund
        except stripe.error.StripeError as e:
            logger.error(f"Error creating refund: {str(e)}")
            return None
    
    def retrieve_payment_intent(self, payment_intent_id: str) -> Optional[Dict]:
        """Retrieve payment intent details"""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            return intent
        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving payment intent: {str(e)}")
            return None
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> Optional[Dict]:
        """Verify webhook signature and return event"""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, Config.STRIPE_WEBHOOK_SECRET
            )
            return event
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {str(e)}")
            return None
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {str(e)}")
            return None