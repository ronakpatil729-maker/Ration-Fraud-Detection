from datetime import datetime, timezone
from app.extensions import db


class StockMovement(db.Model):
    __tablename__ = 'stock_movements'

    TYPE_ALLOCATION = 'ALLOCATION'
    TYPE_RECEIVED = 'RECEIVED'
    TYPE_ADJUSTMENT = 'ADJUSTMENT'
    TYPE_RETURN = 'RETURN'
    TYPES = [TYPE_ALLOCATION, TYPE_RECEIVED, TYPE_ADJUSTMENT, TYPE_RETURN]

    COMMODITY_RICE = 'Rice'
    COMMODITY_WHEAT = 'Wheat'
    COMMODITY_SUGAR = 'Sugar'
    COMMODITIES = [COMMODITY_RICE, COMMODITY_WHEAT, COMMODITY_SUGAR]

    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('ration_shops.id', ondelete='CASCADE'), nullable=False)
    commodity = db.Column(db.String(32), nullable=False)
    movement_type = db.Column(db.String(20), nullable=False, default=TYPE_RECEIVED)
    quantity = db.Column(db.Float, nullable=False)  # in kg
    batch_no = db.Column(db.String(64), nullable=True)
    reference_doc = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    shop = db.relationship('RationShop', back_populates='stock_movements')

    def __repr__(self):
        return f"<StockMovement {self.commodity} {self.quantity}kg ({self.movement_type}) for Shop #{self.shop_id}>"

