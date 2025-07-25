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
        reset_url = url_for('members.auth_reset_password', token=token, _external=True)
        
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



# MOVED TO BOOKINGS BLUEPRINT: add_home_games_filter moved to app/bookings/utils.py








