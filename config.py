import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    #WTForms key to stop CSRF attacks
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard to guess string' 

    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
        
    # Mail server settings for emailing errors to the administrator
    # See: https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-vii-error-handling
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    ADMINS = ['your-email@example.com']

# Menus
    # A structure holding the menu for the site
    MENU_ITEMS = [
    {'name': 'Home', 'link': 'index'},
    {'name': 'Members', 'link': 'members'},
    {'name': 'Bookings', 'link': 'bookings'},
    {'name': 'More', 'link': 'index', 'submenu': [{'name': 'Subitem 1', 'link': 'index'}, 
                                                    {'name': 'Subitem 2', 'link': 'index'},
                                                    None,
                                                    {'name': 'Subitem 3', 'link': 'index'},
                                                    {'name': 'Subitem 4', 'link': 'index'},
                                                    {'name': 'Subitem 5', 'link': 'index'}]},
]
    # A List holding the contents of the Admin menu
    # Using None to create a separator
    ADMIN_MENU_ITEMS = [
        {"name": "Manage Members", "link": "manage_members"},
        None, 
        {"name": "Write Post", "link": "write_post"},
        {"name": "Manage Posts", "link": "manage_posts"},
        None,
        {"name": "Manage Roles", "link": "manage_roles"}
]

# Config options relating to Posts    
    POSTS_PER_PAGE = 10 # Number of posts to display per page
    POST_EXPIRATION_DAYS = 30 # Default number of days before a post expires   

    # Config options relating to bookings and competitions, etc
    # Number of rinks
    RINKS = 6
    # Define daily session periods
    DAILY_SESSIONS = {
        1: "10:00 - 12:30",
        2: "12:30 - 15:00",
        3: "15:00 - 17:30",
        4: "17:30 - 20:00"
    }
    EVENT_TYPES = {"County Competition": 1,
                    "Club Competition": 2,
                    "League": 3,
                    "Friendly": 4,
                    "Roll Up": 5,
                    "Other": 6
}