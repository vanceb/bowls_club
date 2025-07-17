import os

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY environment variable is required. "
            "Please set it in your .flaskenv file or environment. "
            "Generate a secure key with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Secure file storage paths (outside web root)
    SECURE_STORAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'secure_storage')
    POSTS_STORAGE_PATH = os.path.join(SECURE_STORAGE_PATH, 'posts')
    ARCHIVE_STORAGE_PATH = os.path.join(SECURE_STORAGE_PATH, 'archive')
    POLICY_PAGES_STORAGE_PATH = os.path.join(SECURE_STORAGE_PATH, 'policy_pages')

    # Email configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMINS = ['your-email@example.com']

    # List holding the contents of the main menu
    MENU_ITEMS = [
        {'name': 'News', 'link': 'index'},
        {'name': 'Members', 'link': 'members'},
        {'name': 'Bookings', 'link': 'bookings'},
        {
            'name': 'My Games',
            'submenu': [
                {'name': 'View My Games', 'link': 'my_games'},
                {'name': 'Book Roll-Up', 'link': 'book_rollup'},
            ]
        },
]
    # A List holding the contents of the Admin menu
    # Using None to create a separator
    # Organized by role sections for logical grouping
    ADMIN_MENU_ITEMS = [
        # User Management Section
        {"name": "Manage Members", "link": "manage_members", "roles": ["User Manager"]},
        {"name": "Import Users", "link": "import_users"},
        {"name": "Manage Roles", "link": "manage_roles"},
        None,
        # Content Management Section
        {"name": "Write Post", "link": "write_post", "roles": ["Content Manager"]},
        {"name": "Manage Posts", "link": "manage_posts", "roles": ["Content Manager"]},
        {"name": "Manage Policy Pages", "link": "manage_policy_pages"},
        None,
        # Event Management Section
        {"name": "Manage Events", "link": "manage_events", "roles": ["Event Manager"]},
    ]

# Config options relating to Posts    
    POSTS_PER_PAGE = 10 # Number of posts to display per page
    POST_EXPIRATION_DAYS = 30  # Number of days before posts expire

# How many rinks are there for booking
    RINKS = 6

# How many daily sessions are there 
    DAILY_SESSIONS = {
        1: "10:00am - 1:00pm", 
        2: "1:00pm - 4:00pm",
        3: "4:00pm - 7:00pm", 
        4: "7:00pm - 9:30pm"
    }

# Event types
    EVENT_TYPES = {
        "Social": 1,
        "Competition": 2,
        "League": 3,
        "Friendly": 4,
        "Roll Up": 5,
        "Other": 6
    }
    EVENT_GENDERS = {
        "Gents": 1,
        "Ladies": 2,
        "Mixed": 3,
        "Open": 4
    }
    EVENT_FORMATS = {
        "Singles": 1,
        "Pairs": 2,
        "Triples": 3,
        "Fours - 4 Wood": 4,
        "Fours - 2 Wood": 5
    }
    
    # Team positions based on bowls format
    TEAM_POSITIONS = {
        1: ["Player"],  # Singles
        2: ["Lead", "Skip"],  # Pairs
        3: ["Lead", "Second", "Skip"],  # Triples
        4: ["Lead", "Second", "Third", "Skip"],  # Fours - 4 Wood
        5: ["Lead", "Second", "Third", "Skip"]   # Fours - 2 Wood
    }
    
    # Team availability settings
    AVAILABILITY_DEADLINE_DAYS = 7  # Days before game that players must confirm availability
    
    # Booking venue options
    HOME_AWAY_OPTIONS = {
        "Home": "home",
        "Away": "away", 
        "Neutral": "neutral"
    }
    
    # Standard roles for club management
    STANDARD_ROLES = [
        'User Manager',
        'Content Manager', 
        'Event Manager'
    ]
    
    # Roll-up booking configuration
    ROLLUP_ADVANCE_BOOKING_DAYS = 7  # How many days ahead users can book roll-ups
    ROLLUP_MAX_PLAYERS = 8  # Maximum players per roll-up (including organizer)
    ROLLUP_MIN_PLAYERS = 2  # Minimum players required for a roll-up
    
    # Session cookie security configuration
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() == 'true'  # Only send cookies over HTTPS (can be disabled for dev)
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours in seconds
    SESSION_COOKIE_NAME = 'bowls_session'  # Custom cookie name


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.db')
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False  # Allow HTTP in testing


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://user:pass@localhost/bowls_club'
    SESSION_COOKIE_SECURE = True  # Force HTTPS in production


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
