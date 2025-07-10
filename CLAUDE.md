# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**IMPORTANT: Always activate the virtual environment first before running any Flask commands:**

### Running the Application
```bash
# ALWAYS activate virtual environment first
source venv/bin/activate

# Run the Flask development server
flask run
# or
python bowls.py
```

### Database Operations
```bash
# ALWAYS activate virtual environment first
source venv/bin/activate

# Create database migration
flask db migrate -m "description of changes"

# Apply database migrations
flask db upgrade

# Access Flask shell with pre-loaded context
flask shell
```

### Flask Environment Setup
```bash
# ALWAYS activate virtual environment first
source venv/bin/activate

# Set Flask app environment variable (if needed)
export FLASK_APP=bowls.py
export FLASK_ENV=development
```

### Testing and Development Notes

**IMPORTANT: When testing Flask forms programmatically, avoid CSRF failures:**

- **DO NOT** instantiate WTForms directly in test scripts (EventForm(), BookingForm(), etc.)
- Forms use Flask-WTF with CSRF protection that requires HTTP request context
- **Instead, test the underlying models and database operations:**

```python
# ✅ GOOD - Test models and database operations
from app import app, db
from app.models import Event, Booking

with app.app_context():
    events = db.session.scalars(sa.select(Event)).all()
    # Test model functionality, relationships, queries
    
# ❌ BAD - Avoid instantiating forms outside request context
from app.forms import EventForm
form = EventForm()  # This will cause CSRF RuntimeError
```

- **For route testing:** Use Flask's test client or run the development server
- **For form testing:** Test via HTTP requests, not direct instantiation

## CSRF (Cross-Site Request Forgery) Notes

- Always use Flask-WTF's CSRF protection for forms
- Generate CSRF tokens for each form submission
- Validate CSRF tokens on the server-side
- Do not disable CSRF protection in production environments
- Use secret key to sign and validate CSRF tokens
- Regenerate CSRF tokens on each form render
- Implement proper error handling for CSRF token validation failures

## Application Architecture

[... rest of the existing file content remains unchanged ...]