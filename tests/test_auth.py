from flask import url_for
from app.extensions import db
from app.models.user import User


def test_login_page_renders(client):
    """Test that login page is accessible and contains portal elements."""
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert b"PDS Portal Login" in response.data
    assert b"Username or Official Email" in response.data


def test_admin_successful_login(client, admin_user):
    """Test admin login redirects to admin dashboard."""
    response = client.post('/auth/login', data={
        'identifier': 'admin_test',
        'password': 'AdminPass@123'
    }, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'] == '/admin/dashboard'


def test_dealer_successful_login(client, dealer_user):
    """Test dealer login redirects to dealer dashboard."""
    response = client.post('/auth/login', data={
        'identifier': 'dealer_test',
        'password': 'DealerPass@123'
    }, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'] == '/dealer/dashboard'


def test_login_with_email_identifier(client, admin_user):
    """Test that users can log in using their email address."""
    response = client.post('/auth/login', data={
        'identifier': 'admin@test.gov.in',
        'password': 'AdminPass@123'
    }, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'] == '/admin/dashboard'


def test_login_invalid_password(client, admin_user):
    """Test that wrong password returns 401 with error message."""
    response = client.post('/auth/login', data={
        'identifier': 'admin_test',
        'password': 'IncorrectPassword'
    }, follow_redirects=True)

    assert response.status_code == 401
    assert b"Invalid username/email or password." in response.data


def test_login_nonexistent_user(client, app):
    """Test that non-existent username returns 401 with error message."""
    response = client.post('/auth/login', data={
        'identifier': 'ghost_user',
        'password': 'AnyPassword'
    }, follow_redirects=True)

    assert response.status_code == 401
    assert b"Invalid username/email or password." in response.data


def test_login_missing_fields_validation(client):
    """Test that empty login submissions are rejected with 400."""
    response = client.post('/auth/login', data={
        'identifier': '',
        'password': ''
    }, follow_redirects=True)

    assert response.status_code == 400
    assert b"Username or Email is required." in response.data
    assert b"Password is required." in response.data


def test_login_deactivated_account(client, app):
    """Test that inactive users cannot log in."""
    with app.app_context():
        inactive = User(
            username='suspended_user',
            email='suspended@test.gov.in',
            full_name='Suspended Officer',
            role=User.ROLE_DEALER,
            is_active=False
        )
        inactive.set_password('Pass@123')
        db.session.add(inactive)
        db.session.commit()

    response = client.post('/auth/login', data={
        'identifier': 'suspended_user',
        'password': 'Pass@123'
    }, follow_redirects=True)

    assert response.status_code == 403
    assert b"Your account has been deactivated." in response.data


def test_logout(client, admin_user):
    """Test user logout cleans session and redirects to login."""
    # Login first
    client.post('/auth/login', data={
        'identifier': 'admin_test',
        'password': 'AdminPass@123'
    })

    # Logout
    response = client.get('/auth/logout', follow_redirects=True)
    assert response.status_code == 200
    assert b"You have been successfully logged out." in response.data


def test_unauthenticated_protected_route_redirect(client):
    """Test unauthenticated request to protected route redirects to login."""
    response = client.get('/admin/dashboard', follow_redirects=False)
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']


def test_role_based_access_dealer_cannot_access_admin_dashboard(client, dealer_user):
    """Test dealer role is blocked with 403 when trying to access admin dashboard."""
    client.post('/auth/login', data={
        'identifier': 'dealer_test',
        'password': 'DealerPass@123'
    })

    response = client.get('/admin/dashboard')
    assert response.status_code == 403
    assert b"403 - Access Denied" in response.data


def test_role_based_access_admin_cannot_access_dealer_dashboard(client, admin_user):
    """Test admin role is blocked with 403 when trying to access dealer dashboard."""
    client.post('/auth/login', data={
        'identifier': 'admin_test',
        'password': 'AdminPass@123'
    })

    response = client.get('/dealer/dashboard')
    assert response.status_code == 403
    assert b"403 - Access Denied" in response.data


def test_open_redirect_protection(client, admin_user):
    """Verify next parameter ignores external malicious URLs."""
    response = client.post('/auth/login?next=https://evil-attacker.com', data={
        'identifier': 'admin_test',
        'password': 'AdminPass@123'
    }, follow_redirects=False)

    # Should safely fallback to admin dashboard rather than the external domain
    assert response.status_code == 302
    assert response.headers['Location'] == '/admin/dashboard'

