from datetime import datetime, timezone
import uuid
from app.extensions import db


class FraudAlert(db.Model):
    __tablename__ = 'fraud_alerts'

    SEVERITY_LOW = 'LOW'
    SEVERITY_MEDIUM = 'MEDIUM'
    SEVERITY_HIGH = 'HIGH'
    SEVERITY_CRITICAL = 'CRITICAL'
    SEVERITIES = [SEVERITY_LOW, SEVERITY_MEDIUM, SEVERITY_HIGH, SEVERITY_CRITICAL]

    STATUS_DETECTED = 'DETECTED'
    STATUS_INVESTIGATING = 'INVESTIGATING'
    STATUS_RESOLVED = 'RESOLVED'
    STATUS_DISMISSED = 'DISMISSED'
    STATUSES = [STATUS_DETECTED, STATUS_INVESTIGATING, STATUS_RESOLVED, STATUS_DISMISSED]

    ALERT_GHOST_BENEFICIARY = 'GHOST_BENEFICIARY'
    ALERT_BULK_DISPATCH = 'BULK_DISPATCH_ANOMALY'
    ALERT_OFF_HOURS = 'OFF_HOURS_TRANSACTION'
    ALERT_STOCK_DISCREPANCY = 'STOCK_DISCREPANCY'
    ALERT_BIOMETRIC_BYPASS = 'BIOMETRIC_BYPASS_SPIKE'

    id = db.Column(db.Integer, primary_key=True)
    alert_code = db.Column(
        db.String(32),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: f"ALT-{uuid.uuid4().hex[:8].upper()}"
    )
    alert_type = db.Column(db.String(64), nullable=False)
    severity = db.Column(db.String(20), nullable=False, default=SEVERITY_MEDIUM)
    shop_id = db.Column(db.Integer, db.ForeignKey('ration_shops.id', ondelete='CASCADE'), nullable=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('distribution_transactions.id', ondelete='SET NULL'), nullable=True)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_DETECTED)
    confidence_score = db.Column(db.Float, default=0.85, nullable=False)  # 0.0 - 1.0
    detected_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)

    # Relationships
    shop = db.relationship('RationShop', back_populates='fraud_alerts')
    transaction = db.relationship('DistributionTransaction', back_populates='fraud_alerts')

    def __repr__(self):
        return f"<FraudAlert {self.alert_code} [{self.severity}] {self.alert_type}>"

