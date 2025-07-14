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

### Audit Logging Requirements
**CRITICAL: All database changes MUST be logged for security and compliance.**

#### Required for ALL Database Operations:
```python
from app.audit import audit_log_create, audit_log_update, audit_log_delete, audit_log_bulk_operation

# For new records
audit_log_create('ModelName', record.id, 'Description of action', optional_data_dict)

# For updates
audit_log_update('ModelName', record.id, 'Description of action', changes_dict, optional_data_dict)

# For deletions
audit_log_delete('ModelName', record_id, 'Description of action', optional_data_dict)

# For bulk operations
audit_log_bulk_operation('BULK_CREATE', 'ModelName', count, 'Description', optional_data_dict)
```

#### Authentication Events:
```python
from app.audit import audit_log_authentication

# Login/logout events
audit_log_authentication('LOGIN', username, success_boolean, optional_data_dict)
audit_log_authentication('LOGOUT', username, True)
audit_log_authentication('PASSWORD_RESET', username, success_boolean)
```

#### Security Events:
```python
from app.audit import audit_log_security_event

# Access denied, invalid tokens, etc.
audit_log_security_event('ACCESS_DENIED', 'Description', optional_data_dict)
```

#### System Events:
```python
from app.audit import audit_log_system_event

# System initialization, migrations, etc.
audit_log_system_event('INITIALIZATION', 'Description', optional_data_dict)
```

#### Audit Log Format:
All audit logs are written to `instance/logs/audit.log` with format:
```
YYYY-MM-DD HH:MM:SS | INFO | OPERATION | ModelName | ID: xxx | User: username (ID: xxx) | Description | Changes: {...} | Data: {...}
```

#### Examples:
```python
# Member creation
audit_log_create('Member', new_member.id, 
                f'Created member: {new_member.firstname} {new_member.lastname} ({new_member.username})',
                {'status': new_member.status, 'is_admin': new_member.is_admin})

# Member update with changes tracking
changes = get_model_changes(member, form_data)
audit_log_update('Member', member.id, 
                f'Updated member: {member.firstname} {member.lastname}', 
                changes)

# Member deletion
audit_log_delete('Member', member_id, f'Deleted member: {member_name}')
```

### General Security Notes
- Always follow security best practices
- Never introduce code that exposes or logs secrets and keys
- Never commit secrets or keys to the repository
- All database changes must include audit logging
- Use appropriate audit logging functions for all operations

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