# Flask Blueprint Reorganization Guidelines

This document provides guidance for reorganizing Flask application functionality into logical blueprints in this codebase.

## Blueprint Organization Principles

### 1. Logical Functional Grouping
- **Group related functionality together** - All routes, templates, utilities, and logic for a specific domain
- **Minimize cross-blueprint dependencies** - Each blueprint should be as self-contained as possible
- **Follow domain boundaries** - Organize by business functionality, not technical layers

### Examples of Good Blueprint Organization:
- **Members Blueprint**: Authentication, profiles, directory, admin management, role management
- **Events Blueprint**: Event creation, management, scheduling, team assignments
- **Bookings Blueprint**: Booking creation, management, rink assignments, availability
- **Content Blueprint**: Posts, policy pages, news management

### 2. URL Structure and Prefixes

#### Blueprint Registration Pattern:
```python
# In app/__init__.py
from app.members import bp as members_bp
from app.events import bp as events_bp

app.register_blueprint(members_bp, url_prefix='/members')
app.register_blueprint(events_bp, url_prefix='/events')
```

#### Route Organization Within Blueprints:
```python
# In blueprint routes.py
@bp.route('/directory')           # URL: /members/directory
@bp.route('/auth/login')          # URL: /members/auth/login  
@bp.route('/admin/manage')        # URL: /members/admin/manage
@bp.route('/api/v1/search')       # URL: /members/api/v1/search
```

#### URL Prefix Guidelines:
- **Root level routes**: Core functionality (`/directory`, `/apply`)
- **`auth/` prefix**: Authentication-related routes (`/auth/login`, `/auth/profile`)
- **`admin/` prefix**: Administrative functions requiring special permissions
- **`api/v1/` prefix**: API endpoints for AJAX calls (version for future compatibility)

### 3. Directory Structure Standards

```
app/
└── blueprint_name/
    ├── __init__.py          # Blueprint definition and configuration
    ├── routes.py           # All route handlers for the blueprint
    ├── utils.py            # Blueprint-specific utility functions (optional)
    └── templates/          # Blueprint-specific templates
        ├── template1.html
        ├── template2.html
        └── admin_template.html
```

**CRITICAL: Blueprint Template Configuration**
```python
# In blueprint_name/__init__.py
from flask import Blueprint

# MUST specify template_folder for blueprint templates to be found
bp = Blueprint('blueprint_name', __name__, template_folder='templates')

from app.blueprint_name import routes
```

### 4. Template Organization

#### Template Location and Discovery:
- **Templates go in**: `app/blueprint_name/templates/`
- **Blueprint definition MUST include**: `template_folder='templates'`
- **Flask finds them when you call**: `render_template('template_name.html')`

#### Template Naming Convention:
Use descriptive names that include the blueprint context:
- `member_login.html` (not just `login.html`)
- `member_directory.html` (not just `directory.html`)  
- `member_admin_manage.html` (for admin functionality)
- `event_create.html`, `event_manage.html`
- `booking_form.html`, `booking_admin_manage.html`

#### Template References:
```python
# In route handlers - use simple template names
return render_template('member_login.html', form=form)
return render_template('event_create.html', form=form)

# DO NOT use paths like 'members/member_login.html' 
# Flask blueprint template discovery handles the path automatically
```

#### Common Template Issues and Solutions:
**Problem**: `TemplateNotFound` error for blueprint templates
**Solutions**:
1. Ensure `template_folder='templates'` is specified in Blueprint definition
2. Verify template files exist in `app/blueprint_name/templates/`
3. Use simple template names in `render_template()` calls (not paths)
4. Remember: `render_template()` is for templates, `url_for()` is for URLs

### 5. Blueprint Creation Process

#### Step 1: Create Blueprint Structure
```bash
mkdir app/blueprint_name
touch app/blueprint_name/__init__.py
touch app/blueprint_name/routes.py
mkdir app/blueprint_name/templates
```

#### Step 2: Define Blueprint (`__init__.py`)
```python
from flask import Blueprint

bp = Blueprint('blueprint_name', __name__)

from app.blueprint_name import routes
```

#### Step 3: Route Migration Strategy
1. **Identify all related routes** across existing blueprints
2. **Move routes in logical groups** (auth, admin, api, core)
3. **Update route decorators** to use blueprint format
4. **Resolve naming conflicts** between route functions
5. **Update imports** and dependencies

#### Step 4: Template Migration
1. **Move templates** to new blueprint template directory
2. **Rename templates** using descriptive naming convention
3. **Update render_template()** calls in route handlers
4. **Update url_for()** references throughout codebase

#### Step 5: Utility Function Handling
- **Move blueprint-specific utilities** to `blueprint_name/utils.py`
- **Keep shared utilities** in main `app/utils.py`
- **Update imports** in route handlers

#### Step 6: Blueprint Registration
1. **Register new blueprint** in `app/__init__.py`
2. **Remove old blueprint registrations** that are no longer needed
3. **Test all functionality** thoroughly

### 6. Route Migration Best Practices

#### Function Naming Conflicts:
When moving routes from different blueprints, function names may conflict:
```python
# Before (in different blueprints)
def manage_members():  # admin/routes.py
def manage_events():   # admin/routes.py

# After (in new blueprint)
def admin_manage_members():  # members/routes.py
def create_event():          # events/routes.py
```

#### Decorator Updates:
```python
# Old blueprint style
@admin_bp.route('/manage_members')
@login_required
@role_required('User Manager')
def manage_members():

# New blueprint style  
@bp.route('/admin/manage')
@login_required
@role_required('User Manager')
def admin_manage():
```

#### URL Generation Updates:
```python
# Update all url_for() calls
# Old: url_for('admin.manage_members')
# New: url_for('members.admin_manage')

# Old: url_for('auth.login')  
# New: url_for('members.auth_login')
```

### 7. Code Movement Guidelines

#### What Gets Moved:
- **Routes and view functions** - All related HTTP endpoints
- **Templates** - HTML templates used by the blueprint routes
- **Blueprint-specific utilities** - Functions only used by this blueprint
- **Forms** - Forms primarily used by this blueprint (may need to be shared)

#### What Stays Centralized:
- **Models** - Database models stay in `app/models.py`
- **Shared utilities** - Functions used across multiple blueprints
- **Configuration** - App configuration stays in `config.py`
- **Shared forms** - Forms used by multiple blueprints
- **Static assets** - CSS, JS, images stay in `app/static/`

#### Import Updates:
```python
# Update imports when moving utilities
# Old:
from app.utils import generate_reset_token

# New:
from app.members.utils import generate_reset_token
```

### 8. Testing and Validation

#### Testing Checklist:
- [ ] All routes respond correctly with new URLs
- [ ] All templates render properly  
- [ ] All forms submit and validate correctly
- [ ] All url_for() references work
- [ ] All imports resolve correctly
- [ ] User permissions and roles work as expected
- [ ] CSRF protection still functions
- [ ] Audit logging continues to work
- [ ] No broken links in navigation or templates

#### Test Each Route Type:
- **GET routes** - Pages load correctly
- **POST routes** - Forms process and redirect properly  
- **API routes** - JSON responses work for AJAX calls
- **Admin routes** - Permission checking works
- **Auth routes** - Login/logout/password flows work

### 9. Common Pitfalls and Solutions

#### URL Generation Issues:
**Problem**: `url_for()` calls break after blueprint reorganization
**Solution**: Systematically search and update all references:
```bash
# Find all url_for references
grep -r "url_for(" app/templates/
grep -r "url_for(" app/
```

#### Template Not Found Errors:
**Problem**: Templates can't be found after moving
**Solution**: Check template path and naming:
```python
# Correct template reference - Flask finds templates in blueprint/templates/
return render_template('member_login.html')  # Looks in app/members/templates/

# Correct URL generation for redirects
return redirect(url_for('members.auth_login'))  # Points to members blueprint auth_login route
```

#### Import Errors:
**Problem**: Circular imports or missing imports after reorganization
**Solution**: 
- Import blueprints at the end of `__init__.py`
- Use lazy imports in utility functions when needed
- Keep models centralized to avoid circular dependencies

#### Form Import Issues:
**Problem**: Missing form classes when moving routes between blueprints
**Solutions**:
1. **Check form availability**: Verify all imported forms exist in `app/forms.py`
2. **Use FlaskForm for simple cases**: For routes that only need CSRF protection
3. **Manual form processing**: Use `request.form.get()` instead of form fields when forms are complex
4. **Avoid creating duplicate forms**: Reuse existing forms where possible

**Example**:
```python
# Instead of importing non-existent UserRoleForm
from flask_wtf import FlaskForm

# In route handler
form = FlaskForm()  # For CSRF protection only
if form.validate_on_submit():
    role_name = request.form.get('role_name', '').strip()  # Manual processing
```

#### Utility Function Migration:
**Problem**: Functions moved to blueprint utils but still imported from main utils
**Solutions**:
1. **Update imports**: Change import paths when moving functions
2. **Check function usage**: Ensure moved functions are only used by the blueprint
3. **Keep shared utilities centralized**: Don't move functions used by multiple blueprints

**Example**:
```python
# Before: from app.utils import generate_reset_token
# After: from app.members.utils import generate_reset_token
```

#### Form Sharing Issues:  
**Problem**: Forms used by multiple blueprints
**Solution**: Keep shared forms in `app/forms.py` or create a shared forms module

### 10. Documentation Updates

After blueprint reorganization:
- [ ] Update API documentation with new URLs
- [ ] Update user guides with new navigation paths
- [ ] Update development documentation
- [ ] Update deployment scripts if URLs are hardcoded
- [ ] Update any external integrations using the APIs

## Blueprint-Specific Considerations

### Members Blueprint
- **Public routes**: Member application (`/apply`) - no authentication required
- **Auth routes**: Login, logout, password management - require different permission levels
- **Admin routes**: Member management, role assignment - require admin permissions
- **API routes**: Search, role management - for AJAX functionality

### Events Blueprint  
- **Public routes**: Event listings, calendar view
- **Member routes**: Event signup, my events
- **Admin routes**: Event creation, management, team assignments
- **API routes**: Calendar data, availability checks

### Bookings Blueprint
- **Member routes**: View bookings, rink availability
- **Manager routes**: Booking creation, modification
- **Admin routes**: Booking management, rink assignments
- **API routes**: Availability data, booking status

### Content Blueprint
- **Public routes**: View posts, policy pages
- **Admin routes**: Content creation, management
- **API routes**: Content search, metadata

This systematic approach ensures consistent, maintainable blueprint organization while preserving all existing functionality.