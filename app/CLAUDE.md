# Flask Application Development Guidelines

This file provides guidance specific to Flask application development in the `app` directory.

## Development Workflow

**IMPORTANT: Before making ANY changes to Flask application code, follow the GitHub Flow workflow:**

1. **Check current status**: `git status` (should be on main, clean working directory)
2. **Update main branch**: `git checkout main && git pull origin main`
3. **Create feature branch**: `git checkout -b feature/your-feature-name`
4. **Make changes** to Flask app files
5. **Test thoroughly** using `flask run`
6. **Commit changes**: `git add . && git commit -m "descriptive message"`
7. **Push and create PR**: `git push -u origin feature/your-feature-name`
8. **After PR merged**: Clean up branch and return to main

**NEVER work directly on main branch when making Flask application changes.**

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