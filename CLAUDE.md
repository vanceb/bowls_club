# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
# Activate virtual environment first
source venv/bin/activate

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

### Flask Environment Setup
```bash
# Set Flask app environment variable
export FLASK_APP=bowls.py
export FLASK_ENV=development
```

## Application Architecture

### Core Structure
- **Flask application** using SQLAlchemy ORM with SQLite database
- **Template-based rendering** with Jinja2 and Bulma CSS framework
- **Role-based authentication** with Flask-Login and admin decorators
- **Database migrations** managed through Flask-Migrate/Alembic

### Key Models and Relationships
- **Member**: User accounts with roles, authentication, and admin privileges
- **Role**: Many-to-many relationship with Member via `member_roles` table
- **Post**: Content management with markdown/HTML file storage in `app/static/posts/`
- **Booking**: Rink reservations with date/session/rink structure

### Authentication Flow
- Uses `@login_required` decorator for protected routes
- Admin routes protected with custom `@admin_required` decorator
- Password reset via email tokens using `itsdangerous`
- User loader function: `load_user()` in `app/models.py:57`

### Configuration System
- All configurable values in `config.py` including:
  - `RINKS`: Number of bowling rinks (default: 6)
  - `DAILY_SESSIONS`: Time slots for bookings
  - `MENU_ITEMS` and `ADMIN_MENU_ITEMS`: Navigation structure
  - `POSTS_PER_PAGE`: Pagination settings

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

### Role Management
- Many-to-many relationship between Member and Role
- Admin status separate from roles (`is_admin` field)
- Role assignment available in member management interface

### Content Management
- Posts support markdown with metadata parsing
- HTML files generated from markdown for display
- File cleanup when posts are deleted
- Expiration dates and optional pinning functionality