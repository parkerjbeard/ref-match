from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
import enum
from .base import BaseModel


class PaymentType(enum.Enum):
    GAME_PAYMENT = "game_payment"
    PLATFORM_FEE = "platform_fee"
    REFUND = "refund"
    PAYOUT = "payout"


class PaymentStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class Payment(BaseModel):
    __tablename__ = 'payments'
    
    # Parties involved
    payer_id = Column(Integer, ForeignKey('users.id'))
    payee_id = Column(Integer, ForeignKey('users.id'))
    game_id = Column(Integer, ForeignKey('games.id'))
    assignment_id = Column(Integer, ForeignKey('assignments.id'))
    
    # Payment details
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default='USD')
    payment_type = Column(Enum(PaymentType), nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    
    # Stripe details
    stripe_payment_intent_id = Column(String(255))
    stripe_charge_id = Column(String(255))
    stripe_payout_id = Column(String(255))
    stripe_refund_id = Column(String(255))
    
    # Processing details
    processed_at = Column(DateTime)
    failed_at = Column(DateTime)
    failure_reason = Column(String(500))
    
    # Relationships
    payer = relationship("User", back_populates="payments_made", foreign_keys=[payer_id])
    payee = relationship("User", back_populates="payments_received", foreign_keys=[payee_id])
    transactions = relationship("Transaction", back_populates="payment", lazy='dynamic')


class Transaction(BaseModel):
    __tablename__ = 'transactions'
    
    payment_id = Column(Integer, ForeignKey('payments.id'), nullable=False)
    
    # Transaction details
    transaction_type = Column(String(50))  # charge, payout, fee, refund
    amount = Column(Float, nullable=False)
    description = Column(String(500))
    
    # Platform fee tracking
    platform_fee = Column(Float, default=0)
    net_amount = Column(Float)
    
    # Stripe reference
    stripe_transaction_id = Column(String(255))
    
    # Relationships
    payment = relationship("Payment", back_populates="transactions")