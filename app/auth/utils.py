from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user


def role_required(*roles):
    """
    Decorator to restrict route access to users with specified role(s).
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please sign in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            if current_user.role not in roles:
                flash('Access denied: You do not have permission to view this resource.', 'danger')
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Shortcut decorator for admin-only routes."""
    return role_required('admin')(f)


def dealer_required(f):
    """Shortcut decorator for dealer-only routes."""
    return role_required('dealer')(f)

