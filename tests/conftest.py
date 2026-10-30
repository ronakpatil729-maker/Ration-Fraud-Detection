import pytest
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.shop import RationShop
from app.models.beneficiary import Beneficiary


@pytest.fixture
def app():
    """Create and configure a clean Flask application instance for testing."""
    test_app = create_app('testing')

    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Test client for issuing requests."""
    return app.test_client()


@pytest.fixture
def admin_user(app):
    """Create a sample admin user in the database."""
    with app.app_context():
        admin = User(
            username='admin_test',
            email='admin@test.gov.in',
            full_name='Test Administrator',
            role=User.ROLE_ADMIN,
            is_active=True
        )
        admin.set_password('AdminPass@123')
        db.session.add(admin)
        db.session.commit()
        return admin


@pytest.fixture
def dealer_user(app):
    """Create a sample dealer user with mapped ration shop."""
    with app.app_context():
        dealer = User(
            username='dealer_test',
            email='dealer@test.gov.in',
            full_name='Test FPS Dealer',
            role=User.ROLE_DEALER,
            is_active=True
        )
        dealer.set_password('DealerPass@123')
        db.session.add(dealer)
        db.session.flush()

        shop = RationShop(
            shop_no='FPS-TEST-01',
            name='Test Fair Price Shop',
            district='Test District',
            taluk='Test Taluk',
            dealer_id=dealer.id,
            is_active=True
        )
        db.session.add(shop)
        db.session.commit()
        return dealer

