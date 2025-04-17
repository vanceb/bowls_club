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

    # A structure holding the menu for the site
    MENU_ITEMS = [
    {'name': 'Home', 'link': 'index'},
    {'name': 'Members', 'link': 'members'},
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
        {"name": "Manage Roles", "link": "manage_roles"}
]