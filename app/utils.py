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

def generate_reset_token(user):
    """
    Generate a secure reset token for password reset functionality.
    
    Args:
        user (Member): The user object to generate token for.
        
    Returns:
        str: Secure token string that can be used for password reset.
    """
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(user.email, salt='password-reset-salt')

def verify_reset_token(token, expiration=3600):
    """
    Verify a password reset token and return the associated user.
    
    Args:
        token (str): The reset token to verify.
        expiration (int): Token expiration time in seconds (default: 3600).
        
    Returns:
        Member or None: User object if token is valid, None if invalid/expired.
    """
    from app.models import Member
    from app import db
    
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=expiration)
        # Find the user by email
        user = db.session.scalar(sa.select(Member).where(Member.email == email))
        return user
    except Exception:
        return None

def send_reset_email(user, token):
    """
    Send a password reset email to the specified user.
    
    Args:
        user (Member): The user object to send the email to.
        token (str): The reset token to include in the URL.
        
    Returns:
        bool: True if email was sent successfully, False otherwise.
    """
    try:
        from flask import url_for
        
        # Generate the reset URL
        reset_url = url_for('auth.reset_password', token=token, _external=True)
        
        # Create the email message  
        sender = (current_app.config.get('MAIL_DEFAULT_SENDER') or 
                 current_app.config.get('MAIL_USERNAME'))
        
        # Debug logging for sender configuration
        current_app.logger.debug(f"MAIL_DEFAULT_SENDER: {current_app.config.get('MAIL_DEFAULT_SENDER')}")
        current_app.logger.debug(f"MAIL_USERNAME: {current_app.config.get('MAIL_USERNAME')}")
        current_app.logger.debug(f"Using sender: {sender}")
        
        if not sender:
            current_app.logger.error("No email sender configured - missing MAIL_DEFAULT_SENDER and MAIL_USERNAME")
            return False
        
        msg = Message(
            subject='Password Reset Request - Bowls Club',
            recipients=[user.email],
            sender=sender
        )
        
        msg.body = f'''Hello {user.firstname},

You have requested to reset your password for your Bowls Club account.

To reset your password, visit the following link:
{reset_url}

This link will expire in 1 hour for security reasons.

If you did not make this request, simply ignore this email and your password will remain unchanged.

Best regards,
The Bowls Club Team
'''
        
        # Send the email
        mail.send(msg)
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error sending reset email to {user.email}: {str(e)}")
        return False

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


def find_orphaned_policy_pages():
    """
    Find policy page files in secure storage that are not tracked in the database.
    
    Returns:
        list: List of dictionaries containing orphaned file information
    """
    from flask import current_app
    from app.models import PolicyPage
    from app import db
    import sqlalchemy as sa
    
    orphaned_files = []
    policy_dir = current_app.config.get('POLICY_PAGES_STORAGE_PATH')
    
    if not policy_dir or not os.path.exists(policy_dir):
        return orphaned_files
    
    # Get all markdown files in the policy pages directory
    markdown_files = [f for f in os.listdir(policy_dir) if f.endswith('.md')]
    
    # Get all policy page filenames from the database
    db_filenames = set()
    policy_pages = db.session.scalars(sa.select(PolicyPage)).all()
    for page in policy_pages:
        db_filenames.add(page.markdown_filename)
        db_filenames.add(page.html_filename)
    
    # Find orphaned markdown files
    for md_filename in markdown_files:
        if md_filename not in db_filenames:
            # Check if corresponding HTML file exists
            html_filename = md_filename.replace('.md', '.html')
            html_path = os.path.join(policy_dir, html_filename)
            
            # Try to read and parse the markdown file
            md_path = os.path.join(policy_dir, md_filename)
            try:
                with open(md_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse metadata from the markdown file
                metadata, markdown_content = parse_metadata_from_markdown(content)
                
                orphaned_files.append({
                    'markdown_filename': md_filename,
                    'html_filename': html_filename,
                    'has_html': os.path.exists(html_path),
                    'title': metadata.get('title', 'Unknown Title'),
                    'slug': metadata.get('slug', ''),
                    'description': metadata.get('description', ''),
                    'is_active': metadata.get('is_active', True),
                    'show_in_footer': metadata.get('show_in_footer', True),
                    'sort_order': metadata.get('sort_order', 0),
                    'author': metadata.get('author', 'Unknown'),
                    'markdown_content': markdown_content,
                    'file_size': os.path.getsize(md_path),
                    'last_modified': os.path.getmtime(md_path)
                })
            except Exception as e:
                # If we can't parse the file, still include it with basic info
                orphaned_files.append({
                    'markdown_filename': md_filename,
                    'html_filename': html_filename,
                    'has_html': os.path.exists(html_path),
                    'title': f'Corrupted: {md_filename}',
                    'slug': '',
                    'description': f'Error reading file: {str(e)}',
                    'is_active': False,
                    'show_in_footer': False,
                    'sort_order': 0,
                    'author': 'Unknown',
                    'markdown_content': '',
                    'file_size': os.path.getsize(md_path) if os.path.exists(md_path) else 0,
                    'last_modified': os.path.getmtime(md_path) if os.path.exists(md_path) else 0,
                    'error': str(e)
                })
    
    return orphaned_files


def recover_orphaned_policy_page(markdown_filename, current_user_id):
    """
    Recover an orphaned policy page by adding it to the database.
    
    Args:
        markdown_filename (str): Name of the orphaned markdown file
        current_user_id (int): ID of the user performing the recovery
        
    Returns:
        tuple: (success: bool, message: str, policy_page: PolicyPage or None)
    """
    from flask import current_app
    from app.models import PolicyPage
    from app import db
    import sqlalchemy as sa
    
    try:
        # Get the policy pages directory
        policy_dir = current_app.config.get('POLICY_PAGES_STORAGE_PATH')
        if not policy_dir:
            return False, "Policy pages storage path not configured", None
        
        # Read the markdown file
        md_path = os.path.join(policy_dir, markdown_filename)
        if not os.path.exists(md_path):
            return False, f"Markdown file not found: {markdown_filename}", None
        
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse metadata from the markdown file
        metadata, markdown_content = parse_metadata_from_markdown(content)
        
        # Extract metadata with defaults
        title = metadata.get('title', 'Recovered Policy Page')
        slug = metadata.get('slug', '')
        description = metadata.get('description', 'Recovered from orphaned files')
        is_active = metadata.get('is_active', True)
        show_in_footer = metadata.get('show_in_footer', True)
        sort_order = metadata.get('sort_order', 0)
        
        # Generate slug if not provided
        if not slug:
            slug = re.sub(r'[^\w\-_]', '-', title.lower())[:50]
        
        # Check if slug already exists
        existing_page = db.session.scalar(
            sa.select(PolicyPage).where(PolicyPage.slug == slug)
        )
        if existing_page:
            # Make slug unique
            counter = 1
            base_slug = slug
            while existing_page:
                slug = f"{base_slug}-{counter}"
                existing_page = db.session.scalar(
                    sa.select(PolicyPage).where(PolicyPage.slug == slug)
                )
                counter += 1
        
        # Create the policy page record
        html_filename = markdown_filename.replace('.md', '.html')
        policy_page = PolicyPage(
            title=title,
            slug=slug,
            description=description,
            is_active=is_active,
            show_in_footer=show_in_footer,
            sort_order=sort_order,
            author_id=current_user_id,
            markdown_filename=markdown_filename,
            html_filename=html_filename
        )
        
        # Check if HTML file exists, if not, create it
        html_path = os.path.join(policy_dir, html_filename)
        if not os.path.exists(html_path):
            # Convert Markdown to HTML and save
            html_content = markdown2.markdown(markdown_content, extras=["tables"])
            with open(html_path, 'w', encoding='utf-8') as html_file:
                html_file.write(html_content)
        
        # Add to database
        db.session.add(policy_page)
        db.session.commit()
        
        return True, f"Successfully recovered policy page: {title}", policy_page
        
    except Exception as e:
        db.session.rollback()
        return False, f"Error recovering policy page: {str(e)}", None