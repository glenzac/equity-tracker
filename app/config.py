import os
import secrets
from pathlib import Path

basedir = Path(__file__).parent.parent


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    APP_VERSION = '1.0.0'

    # Input validation limits
    MAX_STRING_LENGTH = 255
    MAX_ACCOUNT_NUMBER_LENGTH = 50
    MAX_QUANTITY = 1_000_000_000  # 1 billion max
    MAX_PRICE = 10_000_000  # 10 million max price

    # Upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_EXTENSIONS = ['.xlsx']

    # Price cache settings
    PRICE_CACHE_MARKET_HOURS = 300  # 5 minutes
    PRICE_CACHE_OFF_HOURS = 3600  # 1 hour


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'sqlite:///{basedir / "instance" / "app.db"}'

    # Generate a random secret key for development if not set
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SECRET_KEY = os.environ.get('SECRET_KEY')  # Validated in app factory


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
