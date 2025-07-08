# Standard library imports
import re

# Third-party imports
import markdown2
import yaml
from flask import current_app
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer

# Local application imports
from app import mail

def generate_reset_token(email):
    """
    Generate a secure reset token for password reset functionality.
    
    Args:
        email (str): The email address to generate token for.
        
    Returns:
        str: Secure token string that can be used for password reset.
    """
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='password-reset-salt')

def verify_reset_token(token, expiration=3600):
    """
    Verify a password reset token and extract the email address.
    
    Args:
        token (str): The reset token to verify.
        expiration (int): Token expiration time in seconds (default: 3600).
        
    Returns:
        str or None: Email address if token is valid, None if invalid/expired.
    """
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=expiration)
    except Exception:
        return None
    return email

def send_reset_email(email, reset_url):
    """
    Send a password reset email to the specified email address.
    
    Args:
        email (str): The recipient's email address.
        reset_url (str): The password reset URL to include in the email.
    """
    msg = Message('Password Reset Request', recipients=[email])
    msg.body = f'''To reset your password, visit the following link:
{reset_url}

If you did not make this request, simply ignore this email.
'''
    mail.send(msg)

def render_markdown_with_metadata(markdown_path):
    """
    Render a Markdown file with YAML front matter to HTML.
    
    Args:
        markdown_path (str): Path to the Markdown file to render.
        
    Returns:
        tuple: (metadata dict, html_content str) parsed from the file.
    """
    with open(markdown_path, 'r') as md_file:
        content = md_file.read()

    # Split YAML front matter and Markdown content
    if content.startswith('---'):
        parts = content.split('---', 2)
        metadata = yaml.safe_load(parts[1])  # Parse YAML metadata
        markdown_content = parts[2]
    else:
        metadata = {}
        markdown_content = content

    # Convert Markdown to HTML with extras (e.g., tables)
    html_content = markdown2.markdown(markdown_content, extras=["tables"])
    return metadata, html_content

def parse_metadata_from_markdown(markdown_content):
    """
    Parses metadata and content from a Markdown file with YAML front matter.

    Args:
        markdown_content (str): The content of the Markdown file as a string.

    Returns:
        tuple: A dictionary containing the metadata and a string containing the Markdown content.
    """
    # Check if the content starts with YAML front matter
    if markdown_content.startswith('---'):
        parts = markdown_content.split('---', 2)
        if len(parts) >= 3:
            metadata = yaml.safe_load(parts[1])  # Parse YAML metadata
            content = parts[2].strip()  # The remaining Markdown content
        else:
            metadata = {}
            content = markdown_content.strip()
    else:
        metadata = {}
        content = markdown_content.strip()

    return metadata, content

def sanitize_filename(filename):
    """
    Sanitize a filename by replacing unsafe characters with underscores.
    
    Args:
        filename (str): The filename to sanitize.
        
    Returns:
        str: Sanitized filename safe for filesystem use.
    """
    # Replace unsafe characters with an underscore
    sanitized = re.sub(r'[^\w\-_\.]', '_', filename)
    return sanitized

def filter_admin_menu_by_roles(user):
    """
    Filter admin menu items based on user roles.
    
    Args:
        user: Current user object with roles attribute
        
    Returns:
        List of menu items the user has access to
    """
    from flask import current_app
    
    # Get the full admin menu from config
    admin_menu = current_app.config.get('ADMIN_MENU_ITEMS', [])
    
    # If user is admin, show all menu items
    if user.is_authenticated and user.is_admin:
        return admin_menu
    
    # If user is not authenticated, return empty menu
    if not user.is_authenticated:
        return []
    
    # Get user's role names
    user_role_names = [role.name for role in user.roles]
    
    # Filter menu items based on roles
    filtered_menu = []
    for item in admin_menu:
        # None items are separators - keep them for now
        if item is None:
            filtered_menu.append(item)
        else:
            # Check if item has role requirements
            required_roles = item.get('roles', [])
            
            # If no roles specified, assume admin-only (backward compatibility)
            if not required_roles:
                continue
                
            # Check if user has any of the required roles
            if any(role in user_role_names for role in required_roles):
                filtered_menu.append(item)
    
    # Clean up consecutive separators and trailing separators
    cleaned_menu = []
    prev_was_separator = True  # Start as True to remove leading separators
    
    for item in filtered_menu:
        if item is None:  # Separator
            if not prev_was_separator:
                cleaned_menu.append(item)
                prev_was_separator = True
        else:
            cleaned_menu.append(item)
            prev_was_separator = False
    
    # Remove trailing separator if present
    if cleaned_menu and cleaned_menu[-1] is None:
        cleaned_menu.pop()
    
    return cleaned_menu