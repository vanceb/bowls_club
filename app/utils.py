from itsdangerous import URLSafeTimedSerializer
from flask import current_app
from flask_mail import Message
import markdown2
import yaml
import re
from app import mail

def generate_reset_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='password-reset-salt')

def verify_reset_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=expiration)
    except Exception:
        return None
    return email

def send_reset_email(email, reset_url):
    msg = Message('Password Reset Request', recipients=[email])
    msg.body = f'''To reset your password, visit the following link:
{reset_url}

If you did not make this request, simply ignore this email.
'''
    mail.send(msg)

# Used in the Markdown rendering process in routes.py
def render_markdown_with_metadata(markdown_path):
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
    # Replace unsafe characters with an underscore
    sanitized = re.sub(r'[^\w\-_\.]', '_', filename)
    return sanitized