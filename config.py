import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-long-and-complex-key-that-you-will-never-guess'

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.db')
    
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
]
    # A List holding the contents of the Admin menu
    # Using None to create a separator
    # Organized by role sections for logical grouping
    ADMIN_MENU_ITEMS = [
        # User Management Section
        {"name": "Manage Members", "link": "manage_members", "roles": ["User Manager"]},
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
        1: "9:30am - 12:00pm", 
        2: "1:00pm - 3:30pm",
        3: "4:00pm - 6:00pm", 
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
