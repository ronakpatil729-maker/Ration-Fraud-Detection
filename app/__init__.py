import os
from flask import Flask, render_template
from app.config import config_by_name
from app.extensions import db, login_manager
from app import models  # noqa: F401 - ensure models are registered


def create_app(config_name=None):
    """Application factory for Ration Fraud Detection System."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    flask_app = Flask(__name__)
    flask_app.config.from_object(config_by_name.get(config_name, config_by_name['default']))

    # Initialize extensions
    db.init_app(flask_app)
    login_manager.init_app(flask_app)

    # Register blueprints
    from app.auth import auth_bp
    from app.main import main_bp
    from app.admin import admin_bp
    from app.dealer import dealer_bp

    flask_app.register_blueprint(auth_bp)
    flask_app.register_blueprint(main_bp)
    flask_app.register_blueprint(admin_bp)
    flask_app.register_blueprint(dealer_bp)

    # Global context processor
    @flask_app.context_processor
    def inject_global_data():
        return {
            'app_name': flask_app.config.get('APP_NAME', 'Ration Fraud Detection System')
        }

    # Error handlers
    @flask_app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @flask_app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @flask_app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500

    # Ensure tables are created when running the app
    with flask_app.app_context():
        db.create_all()

    return flask_app
