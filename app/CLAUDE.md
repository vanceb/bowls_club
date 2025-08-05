# Flask Application Development Guidelines

This file provides guidance specific to Flask application development in the `app` directory.

## Flask Blueprint Architecture

**This application uses Flask Blueprints for modular organization:**

### Current Blueprint Structure
- **`api`** - RESTful API endpoints for AJAX functionality
- **`bookings`** - Booking-centric event and rink management (consolidated from events)
- **`content`** - Content management for posts and policy pages
- **`main`** - Core application routes and home page (legacy/overlapped with root)
- **`members`** - Member management, profiles, directory, and authentication
- **`pools`** - Pool management and specialist event functionality
- **`rollups`** - Roll-up booking functionality
- **`teams`** - Team management and player assignments

### Blueprint Organization Principles
- **Logical functional grouping** - Group related functionality together
- **Minimize cross-blueprint dependencies** - Each blueprint should be self-contained
- **Follow domain boundaries** - Organize by business functionality, not technical layers

### Blueprint Directory Structure
```
app/
└── blueprint_name/
    ├── __init__.py          # Blueprint definition with template_folder='templates'
    ├── routes.py           # All route handlers for the blueprint
    ├── forms.py            # Blueprint-specific forms (optional)
    ├── utils.py            # Blueprint-specific utilities (optional)
    └── templates/          # Blueprint-specific templates
        └── template_name.html
```

### Blueprint URL Structure
- **Root level**: Core functionality (`/directory`, `/apply`)
- **`auth/` prefix**: Authentication routes (`/auth/login`, `/auth/profile`)
- **`admin/` prefix**: Administrative functions requiring special permissions
- **`api/v1/` prefix**: API endpoints for AJAX calls (versioned for compatibility)

### Blueprint Template Configuration
```python
# In blueprint_name/__init__.py - CRITICAL: Must specify template_folder
from flask import Blueprint

bp = Blueprint('blueprint_name', __name__, template_folder='templates')

from app.blueprint_name import routes
```

### Blueprint Registration
```python
# In app/__init__.py
from app.members import bp as members_bp
from app.bookings import bp as bookings_bp
from app.teams import bp as teams_bp

app.register_blueprint(members_bp, url_prefix='/members')
app.register_blueprint(bookings_bp, url_prefix='/bookings')
app.register_blueprint(teams_bp, url_prefix='/teams')
```

## Application Structure

### Core Files
- `__init__.py` - Flask app factory and configuration
- `routes.py` - URL routes and view functions
- `models.py` - SQLAlchemy database models
- `forms.py` - WTForms form definitions
- `utils.py` - Utility functions and helpers
- `errors.py` - Error handlers

## Database Development

### Model Guidelines
- Use SQLAlchemy ORM for all database operations
- Follow existing naming conventions for tables and columns
- Include proper relationships with foreign keys
- Add appropriate indexes for performance

### Migration Workflow
```bash
# Create migration after model changes
flask db migrate -m "description of changes"

# Review generated migration file before applying
# Apply migration to database
flask db upgrade
```

### Query Best Practices
```python
# Use select() for queries
users = db.session.scalars(sa.select(Member).where(Member.status == 'Active')).all()

# Use proper joins for relationships
bookings = db.session.scalars(
    sa.select(Booking)
    .join(Event)
    .where(Event.name == 'League Match')
).all()
```

### Database Audit Logging
**CRITICAL: All database modifications MUST be logged immediately after commit.**

#### Required Import:
```python
from app.audit import audit_log_create, audit_log_update, audit_log_delete, audit_log_bulk_operation
```

#### Transaction Pattern with Audit Logging:
```python
# For single record operations
try:
    # Database operation
    db.session.add(new_record)
    db.session.commit()
    
    # REQUIRED: Audit log immediately after successful commit
    audit_log_create('ModelName', new_record.id, 'Description of action')
    
except Exception as e:
    db.session.rollback()
    # Error handling
    raise e

# For bulk operations
try:
    # Multiple database operations
    for item in items:
        db.session.add(item)
    db.session.commit()
    
    # REQUIRED: Audit log bulk operation
    audit_log_bulk_operation('BULK_CREATE', 'ModelName', len(items), 'Description')
    
except Exception as e:
    db.session.rollback()
    raise e
```

#### Update Logging Pattern:
```python
# Update the record
existing_record.field1 = new_value1
existing_record.field2 = new_value2
db.session.commit()

# REQUIRED: Audit log the update
audit_log_update('ModelName', existing_record.id, 'Description of what was updated')
```

## Forms Development

### Form Definition Guidelines
- Extend FlaskForm for all forms
- Use appropriate field types and validators
- Include CSRF protection (automatic with FlaskForm)
- Use choices from app.config for dynamic options

### Custom Validation
```python
def validate_field_name(self, field):
    # Custom validation logic
    existing = db.session.scalar(sa.select(Model).where(Model.field == field.data))
    if existing:
        raise ValidationError('Value already exists')
```

### Dynamic Form Generation
- Use factory functions for complex dynamic forms
- Populate choices in `__init__` method
- Access app.config within form initialization

## Routes Development

### Route Organization
- Group related routes together
- Use appropriate HTTP methods (GET, POST)
- Include proper decorators (@login_required, @admin_required)
- Handle form validation and errors properly
- **ALWAYS include audit logging for database operations**

### Route Security
```python
@app.route('/admin/route')
@login_required
@admin_required
def admin_function():
    # Admin-only functionality
    pass

@app.route('/route/<int:id>')
@login_required
def user_function(id):
    # Verify user can access this resource
    resource = db.session.get(Model, id)
    if not resource or not user_can_access(resource):
        audit_log_security_event('ACCESS_DENIED', f'Unauthorized access attempt to resource {id}')
        abort(403)
    return render_template('template.html', resource=resource)
```

### Audit Logging in Routes
**MANDATORY: All database operations in routes MUST include audit logging.**

#### Database Operation Pattern:
```python
from app.audit import audit_log_create, audit_log_update, audit_log_delete

@app.route('/create_item', methods=['POST'])
@login_required
def create_item():
    # Create new record
    new_item = Model(name=form.name.data)
    db.session.add(new_item)
    db.session.commit()
    
    # REQUIRED: Audit log the creation
    audit_log_create('Model', new_item.id, f'Created item: {new_item.name}')
    
    return redirect(url_for('list_items'))

@app.route('/update_item/<int:id>', methods=['POST'])
@login_required
def update_item(id):
    item = db.session.get(Model, id)
    
    # Update the item
    item.name = form.name.data
    item.status = form.status.data
    db.session.commit()
    
    # REQUIRED: Audit log the update
    audit_log_update('Model', item.id, f'Updated item: {item.name}')
    
    return redirect(url_for('list_items'))

@app.route('/delete_item/<int:id>', methods=['POST'])
@login_required
def delete_item(id):
    item = db.session.get(Model, id)
    item_name = item.name
    
    db.session.delete(item)
    db.session.commit()
    
    # REQUIRED: Audit log the deletion
    audit_log_delete('Model', id, f'Deleted item: {item_name}')
    
    return redirect(url_for('list_items'))
```

#### Authentication Route Pattern:
```python
@app.route('/login', methods=['POST'])
def login():
    if user and user.check_password(form.password.data):
        login_user(user)
        audit_log_authentication('LOGIN', user.username, True)
        return redirect(url_for('dashboard'))
    else:
        audit_log_authentication('LOGIN', form.username.data, False)
        flash('Invalid credentials')
        return redirect(url_for('login'))
```

### JSON API Routes
```python
@app.route('/api/data')
@login_required
def api_data():
    try:
        data = get_data()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

## Utility Functions

### File Organization
- Keep utilities in `utils.py`
- Group related functions together
- Use proper error handling
- Include docstrings for complex functions

### Security Utilities
- Path validation for file operations
- HTML sanitization for user content
- Token generation and verification
- Email sending functionality

## Error Handling

### Error Pages
- Custom error pages in `templates/`
- Proper HTTP status codes
- User-friendly error messages
- Logging for debugging

### Exception Handling
```python
try:
    # Database operation
    db.session.commit()
    flash('Success message', 'success')
except Exception as e:
    db.session.rollback()
    flash('Error occurred', 'danger')
    current_app.logger.error(f'Database error: {str(e)}')
```

## Configuration Management

### App Config Usage
```python
# Access configuration values
max_rinks = current_app.config.get('RINKS', 6)
club_name = current_app.config.get('CLUB_NAME', 'Bowls Club')

# Use config for dynamic form choices
session_choices = current_app.config.get('DAILY_SESSIONS', {})
```

### Environment Variables
- Sensitive data in environment variables
- Default values in config.py
- Never commit secrets to repository

## Role-Based Access Control

### Decorator Usage
```python
@role_required('Event Manager', 'Booking Manager')
def event_management():
    # Function accessible to users with specified roles
    pass
```

### Permission Checking
```python
# Check permissions in templates and routes
if current_user.is_authenticated and current_user.has_role('Admin'):
    # Admin functionality
    pass
```

## Testing Guidelines

### Model Testing
```python
# Test within application context
with app.app_context():
    member = Member(username='test', email='test@example.com')
    db.session.add(member)
    db.session.commit()
    
    # Test relationships and queries
    assert member.id is not None
```

### Route Testing
```python
# Use Flask test client
with app.test_client() as client:
    response = client.post('/login', data={'username': 'test', 'password': 'test'})
    assert response.status_code == 200
```

## Code Style Standards

### Python Import Organization (PEP 8)
```python
# Standard library imports
import os
from datetime import datetime, timedelta
from functools import wraps

# Third-party imports
import sqlalchemy as sa
from flask import render_template, flash, redirect, url_for
from flask_login import current_user, login_user

# Local application imports
from app import app, db
from app.forms import LoginForm, MemberForm
from app.models import Member, Role
from app.utils import generate_reset_token
```

### Variable Naming Standards
- Use `snake_case` for Python variables and functions
- Use `UPPER_CASE` for constants in config.py
- Use descriptive names that explain purpose
- Avoid abbreviations unless widely understood

### Function Documentation
```python
def generate_reset_token(email):
    """
    Generate a secure reset token for password reset functionality.
    
    Args:
        email (str): The email address to generate token for.
        
    Returns:
        str: Secure token string for password reset.
    """
    # Implementation here

@app.route('/logout')
def logout():
    """
    Route: Logout
    - Logs out current user and redirects to home page
    - Clears user session
    """
    # Implementation here
```

## Blueprint Migration Guidelines

### When Creating New Blueprints
1. **Create directory structure** with proper template folder
2. **Move related routes** in logical groups (auth, admin, api, core)
3. **Update route decorators** to use blueprint format
4. **Resolve naming conflicts** between route functions
5. **Move templates** and update `render_template()` calls
6. **Update all `url_for()`** references throughout codebase
7. **Test all functionality** thoroughly

### Common Blueprint Issues
- **TemplateNotFound**: Ensure `template_folder='templates'` in blueprint definition
- **URL generation errors**: Update all `url_for()` calls with new blueprint names
- **Import errors**: Check circular imports and update import paths
- **Form import issues**: Verify forms exist in `app/forms.py` or use FlaskForm for CSRF only

### Template Organization
- **Templates location**: `app/blueprint_name/templates/`
- **Naming convention**: Use descriptive names (`member_login.html`, `booking_create.html`)
- **Template references**: Use simple names in `render_template()` calls
- **URL generation**: Use `url_for('blueprint.function_name')` format

### Route Migration Best Practices
```python
# Function naming conflicts resolution
# Before (in different blueprints)
def manage_members():  # admin/routes.py
def manage_bookings(): # admin/routes.py

# After (in new blueprint)
def admin_manage_members():  # members/routes.py
def create_booking():        # bookings/routes.py

# Decorator updates
# Old: @admin_bp.route('/manage_members')
# New: @bp.route('/admin/manage')

# URL generation updates
# Old: url_for('admin.manage_members')
# New: url_for('members.admin_manage')
```

## Performance Considerations

### Database Optimization
- Use proper indexes on frequently queried columns
- Avoid N+1 queries with eager loading
- Use pagination for large result sets
- Monitor query performance

### Caching
- Cache expensive operations where appropriate
- Use Flask-Caching for route-level caching
- Cache static content with proper headers