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

## Application Architecture

### Core Structure
- **Flask application** using SQLAlchemy ORM with SQLite database
- **Template-based rendering** with Jinja2 and Bulma CSS framework
- **Role-based authentication** with Flask-Login and admin decorators
- **Database migrations** managed through Flask-Migrate/Alembic

### Key Models and Relationships
- **Member**: User accounts with roles, authentication, and admin privileges
  - Many-to-many relationship with Role via `member_roles` table
  - Many-to-many relationship with Event via `event_member_managers` table (for event management)
- **Role**: Defines user permissions and capabilities
  - Standard roles include: "Content Manager", "Event Manager", "User Manager"
  - Members assigned roles determine their system capabilities
- **Event**: Event management with member-based event managers
  - Uses Member/Role architecture instead of separate EventManager model
  - Event managers are Members with "Event Manager" role
  - **Fields**: name, event_type, gender, format, scoring, created_at
  - **Enums**: Gender (Gents/Ladies/Mixed/Open), Format (Singles/Pairs/Triples/Fours-4Wood/Fours-2Wood)
  - **Defaults**: gender=4 (Open), format=5 (Fours - 2 Wood)
- **Post**: Content management with markdown/HTML file storage in `app/static/posts/`
- **Booking**: Rink reservations with date/session/rink structure linked to Events

### Authentication Flow
- Uses `@login_required` decorator for protected routes
- Admin routes protected with custom `@admin_required` decorator
- Password reset via email tokens using `itsdangerous`
- User loader function: `load_user()` in `app/models.py:57`

### Configuration System
- All configurable values in `config.py` including:
  - `RINKS`: Number of bowling rinks (default: 6)
  - `DAILY_SESSIONS`: Time slots for bookings
  - `MENU_ITEMS` and `ADMIN_MENU_ITEMS`: Navigation structure with role-based filtering
  - `POSTS_PER_PAGE`: Pagination settings
  - `EVENT_TYPES`: Enumerated event types (Social, Competition, League, etc.)
  - `EVENT_GENDERS`: Gender categories (Gents=1, Ladies=2, Mixed=3, Open=4)
  - `EVENT_FORMATS`: Game formats (Singles=1, Pairs=2, Triples=3, Fours-4Wood=4, Fours-2Wood=5)
- **Role-Based Admin Menu**: Menu items include `roles` field for dynamic filtering

### Template Architecture
- All templates extend `base.html` for consistent layout
- Bulma CSS framework for responsive design
- Custom CSS overrides in `app/static/css/custom.css`
- Dynamic menu generation from config variables
- Favicon files in `app/static/images/`

### File Storage Patterns
- **Posts**: Markdown files stored in `app/static/posts/` with timestamp-based naming
- **Images**: Static assets in `app/static/images/`
- **Database**: SQLite file `app.db` in project root

### Error Handling
- Custom error pages: 403.html, 404.html, 500.html
- Email logging for production errors (when debug=False)
- Rotating file logs in `logs/bowls.log`

## Development Patterns

### Database Queries
- Use SQLAlchemy 2.0 syntax: `sa.select(Model).where()`
- Session access: `db.session.scalars(query).all()`
- Pagination handled in routes with `POSTS_PER_PAGE` from config

### Form Handling
- WTForms classes defined in `app/forms.py`
- CSRF protection via `SECRET_KEY` configuration
- Form validation and error display integrated with Bulma styles

### Route Organization
- All routes in `app/routes.py` with docstring descriptions
- Admin routes use `@admin_required` decorator
- Utility functions in `app/utils.py`

### File Naming Conventions
- Post files: `{timestamp}_{sanitized_title}.{md|html}`
- Template comments listing which routes use each template
- Function docstrings describing purpose, inputs, outputs, and errors

## Important Implementation Details

### Booking System
- Bookings table structure: date + session + rink
- Sessions defined in `config.py` `DAILY_SESSIONS`
- Rink count configurable via `RINKS` in config
- Booking conflicts handled at database level

### Role-Based System Architecture
- **Core Principle**: All user capabilities managed through Member/Role relationships
- **Standard Roles**:
  - "Content Manager": Can create/edit posts and content
  - "Event Manager": Can manage events and be assigned as event organizers
  - "User Manager": Can manage member accounts, roles, and user permissions
- **Event Management**: 
  - Event managers are Members with "Event Manager" role
  - Forms dynamically populate with Members who have appropriate roles
  - No separate user management systems - everything uses Member model
- **Role Assignment**: Available through member management interface
- **Admin Status**: Separate from roles via `is_admin` field for system administration
- **Dynamic Admin Menu**: Automatically filtered based on user roles
  - Admins see all menu items regardless of roles
  - Non-admin users only see items matching their assigned roles
  - Menu separators cleaned up automatically (no orphaned dividers)
  - **Organized by Role Sections**: User Management, Content Management, Event Management
  - Clear separation between different functional areas

### Content Management
- Posts support markdown with metadata parsing
- HTML files generated from markdown for display
- File cleanup when posts are deleted
- Expiration dates and optional pinning functionality

### UI/UX Patterns
- **Inline Forms**: Date inputs and action buttons use horizontal Bulma columns layout
- **Auto-calculation**: End date automatically set to start date + 7 days in bookings
- **Auto-refresh**: Data reloads automatically when key inputs change
- **Dynamic Forms**: Dropdown choices populated from database queries with role filtering
- **Default Handling**: JavaScript sets appropriate defaults when clearing forms

### Database Migration Practices
- **SQLite NOT NULL Constraints**: Always use `server_default='value'` when adding NOT NULL columns
- **Enumerated Fields**: Store as integers with human-readable mappings in config.py
- **Default Values**: Specify sensible defaults for new columns (e.g., format=5 for "Fours - 2 Wood")
- **Migration Patterns**: Handle existing data gracefully with server defaults before applying constraints

### Test Data Structure
- **19 Total Members**: Mix of Full (11), Social (2), Life (1), Pending (5) statuses
- **Role Distribution**: 8 Event Managers, 6 Content Managers, 3 User Managers, 6 without specific roles
- **Test Credentials**: All test members use password "password123" for development
- **Contact Data**: Realistic names, unique emails (@example.com), sequential phone numbers
- **Event Associations**: 10 bookings distributed across 3 events with proper event_id relationships

## Coding Rules and Style Fixes

- **Code Quality Improvements**:
  - Consistently use SQLAlchemy 2.0 query syntax with `sa.select(Model)` instead of legacy query methods
  - Always use `db.session.scalars()` and `.all()` for query result retrieval
  - Prefer type hints for function arguments and return values
  - Use f-strings for string formatting instead of `.format()` or `%` formatting
  - Implement proper error handling with try/except blocks
  - Use `isinstance()` for type checking instead of `type()`
  - Avoid direct database query modifications outside of model methods
  - Use `@property` decorators for computed model attributes
  - Implement clear docstrings for all functions and methods
  - Follow PEP 8 naming conventions strictly
  - Use context managers for database sessions and file operations
  - Implement logging instead of print statements for debugging
  - Use list comprehensions and generator expressions for more concise code
  - Minimize the use of global variables and state
  - Prefer composition over inheritance in class design
  - Use type annotations consistently across the project
  - Implement proper input validation for all form and API inputs
  - Use enum classes for predefined sets of constants
  - Implement proper dependency injection for better testability
  - Use `pathlib` for file and path operations instead of `os.path`
  - Implement proper error classes for custom exceptions