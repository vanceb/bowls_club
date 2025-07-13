# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment Setup

**CRITICAL: Always activate the virtual environment first before running any Flask commands:**

```bash
# ALWAYS activate virtual environment first
source venv/bin/activate

# Set Flask app environment variable (if needed)
export FLASK_APP=bowls.py
export FLASK_ENV=development
```

## Development Commands

### Running the Application
```bash
# Run the Flask development server
flask run
# or
python bowls.py
```

### Database Operations
```bash
# Create database migration
flask db migrate -m "description of changes"

# Apply database migrations
flask db upgrade

# Access Flask shell with pre-loaded context
flask shell
```

## Package Management

**IMPORTANT: Always regenerate requirements.txt when adding new packages**

### Adding New Packages
1. **Install the package:**
   ```bash
   pip install package-name
   ```

2. **IMMEDIATELY regenerate requirements.txt:**
   ```bash
   pip freeze > requirements.txt
   ```

3. **Commit both the code changes AND the updated requirements.txt**

### Recreating Environment from Scratch
```bash
# Create new virtual environment
python -m venv venv

# Activate virtual environment  
source venv/bin/activate

# Install all packages from requirements.txt
pip install -r requirements.txt
```

**Why This Matters:**
- Ensures other developers can recreate identical environments
- Prevents "works on my machine" issues
- Required for deployment and CI/CD processes
- Maintains package version consistency across environments

## Testing Guidelines

**IMPORTANT: When testing Flask forms programmatically, avoid CSRF failures:**

- **DO NOT** instantiate WTForms directly in test scripts (EventForm(), BookingForm(), etc.)
- Forms use Flask-WTF with CSRF protection that requires HTTP request context
- **Instead, test the underlying models and database operations**
- **For route testing:** Use Flask's test client or run the development server
- **For form testing:** Test via HTTP requests, not direct instantiation

*See `app/CLAUDE.md` for detailed testing examples and guidelines.*

## Security Guidelines

### CSRF (Cross-Site Request Forgery) Protection
- Always use Flask-WTF's CSRF protection for forms
- Generate CSRF tokens for each form submission
- Validate CSRF tokens on the server-side
- Do not disable CSRF protection in production environments
- Use secret key to sign and validate CSRF tokens
- Regenerate CSRF tokens on each form render
- Implement proper error handling for CSRF token validation failures

### General Security Notes
- Always follow security best practices
- Never introduce code that exposes or logs secrets and keys
- Never commit secrets or keys to the repository

## Code Style Guidelines

**IMPORTANT: DO NOT ADD ANY COMMENTS unless asked**

- Follow existing code conventions and patterns
- Mimic code style, use existing libraries and utilities
- When making changes to files, first understand the file's code conventions
- NEVER assume that a given library is available - check that this codebase already uses it
- When creating new components, look at existing components first
- When editing code, look at surrounding context to understand framework choices

## Architecture Notes

- Flask web application with SQLAlchemy ORM
- Bulma CSS framework for UI
- Role-based access control system
- Event and booking management system
- Team management with position-based assignments
- File-based content management for posts and policies

## Hierarchical Documentation

This project uses hierarchical CLAUDE.md files for specific areas:

- `app/CLAUDE.md` - Flask application development guidelines
- `app/templates/CLAUDE.md` - HTML template and frontend development
- `migrations/CLAUDE.md` - Database migration procedures

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.