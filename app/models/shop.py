from datetime import datetime, timezone
from app.extensions import db


class RationShop(db.Model):
    __tablename__ = 'ration_shops'

    id = db.Column(db.Integer, primary_key=True)
    shop_no = db.Column(db.String(32), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    district = db.Column(db.String(64), nullable=False)
    taluk = db.Column(db.String(64), nullable=False)
    pincode = db.Column(db.String(10), nullable=True)
    address = db.Column(db.Text, nullable=True)
    dealer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    dealer = db.relationship('User', back_populates='shops')
    beneficiaries = db.relationship('Beneficiary', back_populates='assigned_shop', lazy='dynamic')
    stock_movements = db.relationship('StockMovement', back_populates='shop', lazy='dynamic', cascade='all, delete-orphan')
    transactions = db.relationship('DistributionTransaction', back_populates='shop', lazy='dynamic')
    fraud_alerts = db.relationship('FraudAlert', back_populates='shop', lazy='dynamic')

    def __repr__(self):
        return f"<RationShop {self.shop_no} - {self.name}>"

