# Standard library imports
import os
import re
import uuid

# Third-party imports
import bleach
import markdown2
import yaml
from flask import current_app
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer

# Local application imports
from app import mail
import sqlalchemy as sa

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

def generate_secure_filename(title, extension=''):
    """
    Generate a secure filename using UUID to prevent path traversal attacks.
    
    Args:
        title (str): The original title (used for reference only).
        extension (str): The file extension (e.g., '.md', '.html').
        
    Returns:
        str: A secure UUID-based filename.
    """
    # Generate a UUID for the filename
    secure_id = str(uuid.uuid4())
    
    # Optional: include a sanitized portion of the title for human readability
    # But limit it to prevent path traversal
    safe_title = re.sub(r'[^\w\-_]', '_', title)[:20]  # Limit to 20 chars
    
    # Create filename with UUID as primary identifier
    if safe_title:
        filename = f"{secure_id}_{safe_title}{extension}"
    else:
        filename = f"{secure_id}{extension}"
    
    return filename

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

def validate_secure_path(filename, base_path):
    """
    Validate that a filename is safe and within the allowed directory.
    
    Args:
        filename (str): The filename to validate.
        base_path (str): The base directory path that files should be within.
        
    Returns:
        str: The validated full path if safe, None if unsafe.
    """
    # Additional sanitization beyond basic filename sanitization
    if not filename or '..' in filename or filename.startswith('/'):
        return None
    
    # Ensure the filename doesn't contain path separators
    if os.path.sep in filename or (os.path.altsep and os.path.altsep in filename):
        return None
        
    # Create the full path
    full_path = os.path.join(base_path, filename)
    
    # Resolve any remaining path traversal attempts
    normalized_path = os.path.normpath(full_path)
    
    # Ensure the normalized path is still within the base directory
    if not normalized_path.startswith(os.path.normpath(base_path)):
        return None
        
    return normalized_path


def add_home_games_filter(query):
    """
    Add a filter to a SQLAlchemy query to exclude away games from bookings.
    
    This utility function centralizes the logic for filtering out away games
    from booking queries used in calendar display and rink availability calculations.
    
    Args:
        query: SQLAlchemy query object that includes Booking model
        
    Returns:
        Modified query with home games filter applied
    """
    from app.models import Booking
    return query.where(sa.or_(Booking.home_away != 'away', Booking.home_away == None))

def get_secure_post_path(filename):
    """
    Get a secure path for post files.
    
    Args:
        filename (str): The post filename.
        
    Returns:
        str: Secure path for the post file, or None if invalid.
    """
    from flask import current_app
    base_path = current_app.config.get('POSTS_STORAGE_PATH')
    return validate_secure_path(filename, base_path)

def get_secure_archive_path(filename):
    """
    Get a secure path for archive files.
    
    Args:
        filename (str): The archive filename.
        
    Returns:
        str: Secure path for the archive file, or None if invalid.
    """
    from flask import current_app
    base_path = current_app.config.get('ARCHIVE_STORAGE_PATH')
    return validate_secure_path(filename, base_path)

def get_secure_policy_page_path(filename):
    """
    Get a secure path for policy page files.
    
    Args:
        filename (str): The policy page filename.
        
    Returns:
        str: Secure path for the policy page file, or None if invalid.
    """
    from flask import current_app
    base_path = current_app.config.get('POLICY_PAGES_STORAGE_PATH')
    return validate_secure_path(filename, base_path)

def sanitize_html_content(html_content):
    """
    Sanitize HTML content to prevent XSS while allowing safe formatting.
    
    Args:
        html_content (str): Raw HTML content to sanitize.
        
    Returns:
        str: Sanitized HTML content safe for rendering.
    """
    # Define allowed HTML tags for blog posts
    allowed_tags = [
        'p', 'br', 'strong', 'em', 'b', 'i', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'a', 'blockquote', 'code', 'pre', 'table', 'thead', 'tbody', 
        'tr', 'th', 'td', 'hr', 'img', 'div', 'span'
    ]
    
    # Define allowed attributes for specific tags
    allowed_attributes = {
        'a': ['href', 'title'],
        'img': ['src', 'alt', 'title', 'width', 'height'],
        'table': ['class'],
        'th': ['class'],
        'td': ['class'],
        'div': ['class'],
        'span': ['class']
    }
    
    # Sanitize the HTML content
    return bleach.clean(html_content, tags=allowed_tags, attributes=allowed_attributes)