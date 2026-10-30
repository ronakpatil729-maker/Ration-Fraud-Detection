from app.extensions import db
from app.models.user import User
from app.models.shop import RationShop
from app.models.beneficiary import Beneficiary
from app.models.stock import StockMovement
from app.models.transaction import DistributionTransaction
from app.models.alert import FraudAlert


def test_user_password_hashing(app):
    """Verify password hashing security and verification logic."""
    with app.app_context():
        u = User(
            username='vigilance_officer',
            email='officer@vigilance.gov.in',
            full_name='Officer Sharma',
            role=User.ROLE_ADMIN
        )
        u.set_password('Secret@Pass123')

        # Password hash should not be plaintext
        assert u.password_hash != 'Secret@Pass123'
        assert u.check_password('Secret@Pass123') is True
        assert u.check_password('WrongPass') is False
        assert u.is_admin is True
        assert u.is_dealer is False


def test_dealer_role_flags(app):
    """Verify dealer role properties."""
    with app.app_context():
        u = User(
            username='fps_owner_1',
            email='owner@fps.gov.in',
            full_name='Dealer Ramesh',
            role=User.ROLE_DEALER
        )
        assert u.is_dealer is True
        assert u.is_admin is False


def test_ration_shop_and_stock_relationship(app):
    """Verify RationShop relationships with dealer and stock movements."""
    with app.app_context():
        dealer = User(
            username='dealer_test_rel',
            email='dealer_rel@test.gov.in',
            full_name='Dealer Rel',
            role=User.ROLE_DEALER
        )
        dealer.set_password('Pass123')
        db.session.add(dealer)
        db.session.flush()

        shop = RationShop(
            shop_no='FPS-TEST-100',
            name='Bangalore Central Depot',
            district='Bengaluru Urban',
            taluk='North',
            dealer_id=dealer.id
        )
        db.session.add(shop)
        db.session.flush()

        stock = StockMovement(
            shop_id=shop.id,
            commodity=StockMovement.COMMODITY_RICE,
            movement_type=StockMovement.TYPE_RECEIVED,
            quantity=1200.0,
            batch_no='BATCH-TEST'
        )
        db.session.add(stock)
        db.session.commit()

        # Check relationships
        assert shop.dealer.username == 'dealer_test_rel'
        assert shop.stock_movements.count() == 1
        assert shop.stock_movements.first().quantity == 1200.0


def test_beneficiary_and_distribution_transaction(app):
    """Verify transaction creation and linking to beneficiary and shop."""
    with app.app_context():
        shop = RationShop(
            shop_no='FPS-TEST-200',
            name='Mysuru Depot',
            district='Mysuru',
            taluk='Central'
        )
        db.session.add(shop)
        db.session.flush()

        beneficiary = Beneficiary(
            ration_card_no='RC-TEST-0001',
            head_of_family='Sunita Kumari',
            aadhaar_hash='synth_hash_001',
            card_category=Beneficiary.CATEGORY_BPL,
            monthly_rice_quota=20.0,
            assigned_shop_id=shop.id
        )
        db.session.add(beneficiary)
        db.session.flush()

        txn = DistributionTransaction(
            shop_id=shop.id,
            beneficiary_id=beneficiary.id,
            commodity='Rice',
            quantity=20.0,
            auth_mode=DistributionTransaction.AUTH_BIOMETRIC,
            biometric_match_score=0.98
        )
        db.session.add(txn)
        db.session.commit()

        assert txn.transaction_code.startswith('TXN-')
        assert txn.status == DistributionTransaction.STATUS_COMPLETED
        assert txn.beneficiary.head_of_family == 'Sunita Kumari'
        assert txn.shop.shop_no == 'FPS-TEST-200'


def test_fraud_alert_creation_and_defaults(app):
    """Verify FraudAlert default values, alert code generation, and linkage."""
    with app.app_context():
        shop = RationShop(
            shop_no='FPS-TEST-300',
            name='Hubballi Depot',
            district='Dharwad',
            taluk='Hubballi'
        )
        db.session.add(shop)
        db.session.flush()

        alert = FraudAlert(
            alert_type=FraudAlert.ALERT_BULK_DISPATCH,
            severity=FraudAlert.SEVERITY_CRITICAL,
            shop_id=shop.id,
            description='Abnormal grain withdrawal threshold surpassed.',
            confidence_score=0.95
        )
        db.session.add(alert)
        db.session.commit()

        assert alert.alert_code.startswith('ALT-')
        assert alert.status == FraudAlert.STATUS_DETECTED
        assert alert.severity == 'CRITICAL'
        assert alert.shop.shop_no == 'FPS-TEST-300'

