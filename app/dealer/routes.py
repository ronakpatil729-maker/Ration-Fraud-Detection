from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.auth.utils import dealer_required
from app.models.shop import RationShop
from app.models.transaction import DistributionTransaction
from app.models.stock import StockMovement

dealer_bp = Blueprint('dealer', __name__, url_prefix='/dealer')


@dealer_bp.route('/dashboard')
@login_required
@dealer_required
def dashboard():
    """Dealer portal dashboard showing assigned shop operations."""
    shop = RationShop.query.filter_by(dealer_id=current_user.id).first()
    recent_transactions = []
    stock_summary = []

    if shop:
        recent_transactions = DistributionTransaction.query.filter_by(shop_id=shop.id)\
            .order_by(DistributionTransaction.created_at.desc()).limit(10).all()
        stock_summary = StockMovement.query.filter_by(shop_id=shop.id)\
            .order_by(StockMovement.created_at.desc()).limit(8).all()

    return render_template(
        'dealer/dashboard.html',
        shop=shop,
        recent_transactions=recent_transactions,
        stock_summary=stock_summary
    )

