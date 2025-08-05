from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
from logging.handlers import SMTPHandler, RotatingFileHandler
import os
from flask_moment import Moment
import sqlalchemy as sa

# Initialize extensions
db = SQLAlchemy()
mail = Mail()
migrate = Migrate()
login = LoginManager()
moment = Moment()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)


def create_app(config_name='development'):
    """Application factory function"""
    app = Flask(__name__)
    
    # Load configuration
    from config import config
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    login.login_view = 'members.auth_login'
    moment.init_app(app)
    limiter.init_app(app)
    
    # Configure logging
    configure_logging(app)
    
    # Register template context processors
    register_template_context_processors(app)
    
    # Register template filters
    register_template_filters(app)
    
    # Register middleware
    register_middleware(app)
    
    # Register blueprints/routes
    register_routes(app)
    
    return app


def configure_logging(app):
    """Configure logging for the application"""
    # Ensure instance/logs directory exists
    logs_dir = os.path.join(app.instance_path, 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Always log to file (even in debug mode)
    app_log_path = os.path.join(logs_dir, 'app.log')
    file_handler = RotatingFileHandler(app_log_path, maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    
    # Set appropriate log level
    if app.debug:
        app.logger.setLevel(logging.DEBUG)
    else:
        app.logger.setLevel(logging.INFO)
    
    # Email notifications for production errors only
    if not app.debug and app.config.get('MAIL_SERVER'):
        auth = None
        if app.config['MAIL_USERNAME'] or app.config['MAIL_PASSWORD']:
            auth = (app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        secure = None
        if app.config['MAIL_USE_TLS']:
            secure = ()
        mail_handler = SMTPHandler(
            mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
            fromaddr='no-reply@' + app.config['MAIL_SERVER'],
            toaddrs=app.config['ADMINS'], subject='Bowls Club Failure',
            credentials=auth, secure=secure)
        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)

    app.logger.info('Bowls Club application startup')

def register_template_context_processors(app):
    """Register template context processors"""
    
    @app.context_processor
    def inject_menu_items():
        """Make menu items and filtered admin menu available to all templates"""
        from flask_login import current_user
        from app.utils import filter_admin_menu_by_roles
        
        filtered_admin_menu = filter_admin_menu_by_roles(current_user)
        return dict(
            menu_items=app.config['MENU_ITEMS'],
            filtered_admin_menu_items=filtered_admin_menu
        )

    @app.context_processor
    def inject_footer_policy_pages():
        """Make footer policy pages available to all templates"""
        import sqlalchemy as sa
        from app.models import PolicyPage
        
        try:
            footer_policy_pages = db.session.scalars(
                sa.select(PolicyPage)
                .where(PolicyPage.is_active == True, PolicyPage.show_in_footer == True)
                .order_by(PolicyPage.sort_order, PolicyPage.title)
            ).all()
        except Exception as e:
            # Handle database errors gracefully (e.g., during tests or initial setup)
            app.logger.debug(f"Could not load footer policy pages: {e}")
            footer_policy_pages = []
        
        return dict(footer_policy_pages=footer_policy_pages)

def register_template_filters(app):
    """Register custom template filters"""
    
    @app.template_filter('from_json')
    def from_json_filter(json_str):
        """Convert JSON string to Python object"""
        if not json_str:
            return []
        try:
            import json
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return []

    @app.template_filter('timestamp_to_date')
    def timestamp_to_date_filter(timestamp):
        """Convert Unix timestamp to human-readable date"""
        try:
            from datetime import datetime
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
        except (ValueError, TypeError, OSError):
            return 'Unknown'
    
    @app.template_filter('parse_datetime')
    def parse_datetime_filter(datetime_str):
        """Parse ISO datetime string to datetime object"""
        try:
            from datetime import datetime
            return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        except (ValueError, TypeError, AttributeError):
            try:
                # Fallback for older datetime strings
                return datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%S.%f')
            except (ValueError, TypeError):
                from datetime import datetime
                return datetime.now()

def register_middleware(app):
    """Register middleware functions"""
    
    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses"""
        # Content Security Policy
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
            "img-src 'self' data:; "
            "connect-src 'self';"
        )
        
        # HTTP Strict Transport Security
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # X-Content-Type-Options
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # X-Frame-Options
        response.headers['X-Frame-Options'] = 'DENY'
        
        # X-XSS-Protection
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer Policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions Policy
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        return response

    @app.before_request
    def track_user_activity():
        """Update last_seen date for authenticated users - only once per day"""
        from flask_login import current_user, logout_user
        from datetime import date
        
        if current_user.is_authenticated:
            # Check if user has been locked out
            if current_user.lockout:
                logout_user()
                from flask import flash, redirect, url_for
                flash('Your account has been locked. Please contact the administrator.', 'error')
                return redirect(url_for('login'))
            
            # Update last_seen date
            today = date.today()
            if current_user.last_seen != today:
                current_user.last_seen = today
                db.session.commit()


def register_routes(app):
    """Register application routes via blueprints"""
    # Import and register blueprints
    from app.main import bp as main_bp
    from app.members import bp as members_bp
    from app.content import bp as content_bp
    from app.bookings import bp as bookings_bp
    from app.teams import bp as teams_bp
    from app.pools import bp as pools_bp
    from app.api import bp as api_bp
    from app.admin import bp as admin_bp
    from app.rollups import bp as rollups_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(members_bp, url_prefix='/members')
    app.register_blueprint(content_bp, url_prefix='/content')
    app.register_blueprint(bookings_bp, url_prefix='/bookings')
    app.register_blueprint(teams_bp, url_prefix='/teams')
    app.register_blueprint(pools_bp, url_prefix='/pools')
    app.register_blueprint(rollups_bp, url_prefix='/rollups')
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
    
    # Register error handlers
    from app.errors import register_error_handlers
    register_error_handlers(app)
    
    # Import models to ensure they're loaded
    from app import models


