from urllib.parse import urlparse, urljoin
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models.user import User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def is_safe_url(target: str) -> bool:
    """Validate that the redirect target is local to prevent open redirect vulnerabilities."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('dealer.dashboard'))

    if request.method == 'POST':
        identifier = (request.form.get('identifier') or '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        # Input validation
        errors = []
        if not identifier:
            errors.append('Username or Email is required.')
        if not password:
            errors.append('Password is required.')

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('auth/login.html', identifier=identifier), 400

        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier.lower())
        ).first()

        if not user or not user.check_password(password):
            flash('Invalid username/email or password.', 'danger')
            return render_template('auth/login.html', identifier=identifier), 401

        if not user.is_active:
            flash('Your account has been deactivated. Please contact an administrator.', 'danger')
            return render_template('auth/login.html', identifier=identifier), 403

        login_user(user, remember=remember)
        flash(f'Welcome back, {user.full_name} ({user.role.title()})!', 'success')

        next_page = request.args.get('next')
        if next_page and is_safe_url(next_page):
            return redirect(next_page)

        if user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('dealer.dashboard'))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been successfully logged out.', 'info')
    return redirect(url_for('auth.login'))

