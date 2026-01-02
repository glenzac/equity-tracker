import os
import logging
import click
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from app.config import config
from app.extensions import db, migrate, limiter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app(config_name=None):
    """Application factory for creating the Flask app."""
    load_dotenv()

    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config[config_name])

    # Validate SECRET_KEY in production
    if config_name == 'production' and not app.config.get('SECRET_KEY'):
        raise ValueError(
            "SECRET_KEY environment variable is required in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    # Register error handlers
    register_error_handlers(app)

    # Context processors
    @app.context_processor
    def inject_version():
        return {'version': app.config.get('APP_VERSION', '1.0.0')}

    # Import models for Flask-Migrate
    from app import models  # noqa: F401

    # Register blueprints
    from app.routes.main import main_bp
    app.register_blueprint(main_bp)

    from app.routes.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api/v1')

    from app.routes.import_export import import_bp
    app.register_blueprint(import_bp, url_prefix='/api/v1/import')

    from app.routes.portfolio import portfolio_bp
    app.register_blueprint(portfolio_bp, url_prefix='/api/v1/portfolio')

    from app.routes.settings import settings_bp
    app.register_blueprint(settings_bp, url_prefix='/api/v1/settings')

    from app.routes.allocations import allocations_bp
    app.register_blueprint(allocations_bp, url_prefix='/api/v1')

    # Register CLI commands
    register_cli_commands(app)

    # Shell context for flask shell
    @app.shell_context_processor
    def make_shell_context():
        from app.models import (
            Broker, Account, Owner, Goal, Sector, Stock,
            Trade, Allocation, RealizedPnL, CorporateAction,
            ImportLog, PriceCache
        )
        return {
            'db': db,
            'Broker': Broker,
            'Account': Account,
            'Owner': Owner,
            'Goal': Goal,
            'Sector': Sector,
            'Stock': Stock,
            'Trade': Trade,
            'Allocation': Allocation,
            'RealizedPnL': RealizedPnL,
            'CorporateAction': CorporateAction,
            'ImportLog': ImportLog,
            'PriceCache': PriceCache,
        }

    return app


def register_cli_commands(app):
    """Register CLI commands for the application."""

    @app.cli.command('seed')
    def seed_command():
        """Seed the database with initial data."""
        from app.models import Sector, Owner, Goal

        click.echo('Seeding sectors...')
        Sector.seed_sectors()

        click.echo('Seeding default owner...')
        default_owner = Owner.query.filter_by(is_default=True).first()
        if not default_owner:
            default_owner = Owner(name='#DEFAULT', is_default=True)
            db.session.add(default_owner)

        click.echo('Seeding default goal...')
        default_goal = Goal.query.filter_by(is_default=True).first()
        if not default_goal:
            default_goal = Goal(name='#UNASSIGNED', is_default=True)
            db.session.add(default_goal)

        db.session.commit()
        click.echo('Database seeded successfully!')

    @app.cli.command('init-db')
    def init_db_command():
        """Initialize the database with all tables and seed data."""
        click.echo('Creating database tables...')
        db.create_all()

        click.echo('Seeding initial data...')
        from app.models import Sector, Owner, Goal

        Sector.seed_sectors()

        default_owner = Owner.query.filter_by(is_default=True).first()
        if not default_owner:
            default_owner = Owner(name='#DEFAULT', is_default=True)
            db.session.add(default_owner)

        default_goal = Goal.query.filter_by(is_default=True).first()
        if not default_goal:
            default_goal = Goal(name='#UNASSIGNED', is_default=True)
            db.session.add(default_goal)

        db.session.commit()
        click.echo('Database initialized successfully!')


def register_error_handlers(app):
    """Register error handlers for the application."""

    @app.errorhandler(400)
    def bad_request(error):
        logger.warning(f"Bad request: {error}")
        return jsonify({
            'status': 'error',
            'message': str(error.description) if hasattr(error, 'description') else 'Bad request'
        }), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'status': 'error',
            'message': 'Resource not found'
        }), 404

    @app.errorhandler(413)
    def request_entity_too_large(error):
        logger.warning(f"File too large: {error}")
        return jsonify({
            'status': 'error',
            'message': 'File too large. Maximum size is 16MB.'
        }), 413

    @app.errorhandler(429)
    def ratelimit_handler(error):
        logger.warning(f"Rate limit exceeded: {request.remote_addr}")
        return jsonify({
            'status': 'error',
            'message': 'Rate limit exceeded. Please try again later.'
        }), 429

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'An internal error occurred'
        }), 500
