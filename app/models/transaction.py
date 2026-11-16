from datetime import datetime, timezone
import uuid
from app.extensions import db


class DistributionTransaction(db.Model):
    __tablename__ = 'distribution_transactions'

    AUTH_BIOMETRIC = 'BIOMETRIC'
    AUTH_OTP = 'OTP'
    AUTH_MANUAL = 'MANUAL'
    AUTH_MODES = [AUTH_BIOMETRIC, AUTH_OTP, AUTH_MANUAL]

    STATUS_COMPLETED = 'COMPLETED'
    STATUS_FLAGGED = 'FLAGGED'
    STATUS_REJECTED = 'REJECTED'
    STATUSES = [STATUS_COMPLETED, STATUS_FLAGGED, STATUS_REJECTED]

    id = db.Column(db.Integer, primary_key=True)
    transaction_code = db.Column(
        db.String(40),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: f"TXN-{uuid.uuid4().hex[:10].upper()}"
    )
    shop_id = db.Column(db.Integer, db.ForeignKey('ration_shops.id', ondelete='CASCADE'), nullable=False)
    beneficiary_id = db.Column(db.Integer, db.ForeignKey('beneficiaries.id', ondelete='CASCADE'), nullable=False)
    commodity = db.Column(db.String(32), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    auth_mode = db.Column(db.String(20), nullable=False, default=AUTH_BIOMETRIC)
    status = db.Column(db.String(20), nullable=False, default=STATUS_COMPLETED)
    biometric_match_score = db.Column(db.Float, nullable=True)  # Synthetic score 0.0 - 1.0
    pos_device_id = db.Column(db.String(32), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    shop = db.relationship('RationShop', back_populates='transactions')
    beneficiary = db.relationship('Beneficiary', back_populates='transactions')
    fraud_alerts = db.relationship('FraudAlert', back_populates='transaction', lazy='dynamic')

    def __repr__(self):
        return f"<Transaction {self.transaction_code} - {self.commodity} {self.quantity}kg ({self.status})>"

