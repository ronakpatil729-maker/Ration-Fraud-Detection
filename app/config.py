import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(os.path.join(BASE_DIR, '.env'))


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-ration-fraud-secure-fallback-key-2026')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    APP_NAME = os.environ.get('APP_NAME', 'Ration Fraud Detection System')

    # Instance path for SQLite
    INSTANCE_DIR = BASE_DIR / 'instance'
    INSTANCE_DIR.mkdir(exist_ok=True)

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{INSTANCE_DIR / 'ration_fraud.db'}"
    )


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class TestingConfig(Config):
    """Testing configuration with isolated in-memory DB."""
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

