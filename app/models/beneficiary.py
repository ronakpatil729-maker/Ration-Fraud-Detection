from datetime import datetime, timezone
from app.extensions import db


class Beneficiary(db.Model):
    __tablename__ = 'beneficiaries'

    CATEGORY_AAY = 'AAY'  # Antyodaya Anna Yojana (Poorest of poor)
    CATEGORY_BPL = 'BPL'  # Below Poverty Line
    CATEGORY_APL = 'APL'  # Above Poverty Line
    CATEGORIES = [CATEGORY_AAY, CATEGORY_BPL, CATEGORY_APL]

    id = db.Column(db.Integer, primary_key=True)
    ration_card_no = db.Column(db.String(32), unique=True, nullable=False, index=True)
    head_of_family = db.Column(db.String(120), nullable=False)
    aadhaar_hash = db.Column(db.String(64), nullable=False)  # Synthetic pseudonymized hash
    card_category = db.Column(db.String(10), nullable=False, default=CATEGORY_BPL)
    family_members_count = db.Column(db.Integer, default=4, nullable=False)
    monthly_rice_quota = db.Column(db.Float, default=20.0, nullable=False)  # in kg
    monthly_wheat_quota = db.Column(db.Float, default=10.0, nullable=False)  # in kg
    monthly_sugar_quota = db.Column(db.Float, default=2.0, nullable=False)   # in kg
    phone = db.Column(db.String(20), nullable=True)
    assigned_shop_id = db.Column(db.Integer, db.ForeignKey('ration_shops.id', ondelete='SET NULL'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    assigned_shop = db.relationship('RationShop', back_populates='beneficiaries')
    transactions = db.relationship('DistributionTransaction', back_populates='beneficiary', lazy='dynamic')

    def __repr__(self):
        return f"<Beneficiary {self.ration_card_no} ({self.card_category}) - {self.head_of_family}>"

