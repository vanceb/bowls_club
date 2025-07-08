# Flask Bowling Club - Coding Style Guide

This document outlines the coding standards, conventions, and best practices for the Flask bowling club management system.

## 📋 Table of Contents

1. [Python Code Standards](#python-code-standards)
2. [Template Standards](#template-standards)
3. [JavaScript Standards](#javascript-standards)
4. [CSS Standards](#css-standards)
5. [Database Standards](#database-standards)
6. [Security Standards](#security-standards)
7. [Documentation Standards](#documentation-standards)

---

## 🐍 Python Code Standards

### Import Organization (PEP 8)

**Structure all Python files with this import order:**

```python
# Standard library imports
import os
import shutil
from datetime import datetime, timedelta, date
from functools import wraps

# Third-party imports
import sqlalchemy as sa
from flask import render_template, flash, redirect, url_for
from flask_login import current_user, login_user
from werkzeug.security import generate_password_hash

# Local application imports
from app import app, db
from app.forms import (
    LoginForm, MemberForm, EditMemberForm
)
from app.models import Member, Role, Post
from app.utils import (
    generate_reset_token, verify_reset_token
)
```

**Rules:**
- ✅ Group imports: Standard library → Third-party → Local
- ✅ Blank lines between groups
- ✅ Break long import lines with parentheses
- ✅ Alphabetical order within groups when practical
- ✅ Use descriptive comments for each section

### Function Documentation

**All functions must have docstrings:**

```python
def generate_reset_token(email):
    """
    Generate a secure reset token for password reset functionality.
    
    Args:
        email (str): The email address to generate token for.
        
    Returns:
        str: Secure token string that can be used for password reset.
    """
    # Implementation here
```

**Route Documentation Format:**

```python
@app.route('/logout')
def logout():
    """
    Route: Logout
    - Logs out the current user and redirects to home page.
    - Clears the user session.
    """
    # Implementation here
```

**Rules:**
- ✅ All public functions must have docstrings
- ✅ Include Args and Returns sections for utility functions
- ✅ Route functions use "Route: Name - Description" format
- ✅ Use consistent indentation and formatting

### Variable Naming

**Rules:**
- ✅ Use snake_case for all Python variables and functions
- ✅ Use UPPER_CASE for constants in config.py
- ✅ Use descriptive names that explain purpose
- ✅ Avoid abbreviations unless widely understood

---

## 🌐 Template Standards

### Form Layout Patterns

**Use semantic grouping for form fields:**

```html
<!-- Use field-body for logically related fields -->
<div class="field-body">
    <div class="field">
        <label class="label">First Name</label>
        <div class="control">
            {{ form.firstname(class="input") }}
        </div>
    </div>
    <div class="field">
        <label class="label">Last Name</label>
        <div class="control">
            {{ form.lastname(class="input") }}
        </div>
    </div>
</div>

<!-- Use columns for responsive layout -->
<div class="columns">
    <div class="column is-half">
        <div class="field">
            <label class="label">Booking Date</label>
            <div class="control">
                {{ form.booking_date(class="input") }}
            </div>
        </div>
    </div>
    <div class="column is-half">
        <div class="field">
            <label class="label">Session</label>
            <div class="control">
                {{ form.session(class="select is-fullwidth") }}
            </div>
        </div>
    </div>
</div>
```

**Rules:**
- ✅ Use `field-body` for logically related fields (names, dates, passwords)
- ✅ Use `columns` for responsive layout and general form structure
- ✅ Consistent error message display with Bulma classes
- ✅ Maintain consistent indentation (4 spaces)

### Button Component Standards

**All action buttons should include icons and consistent structure:**

```html
<!-- Primary Action Button -->
<button type="submit" class="button is-primary">
    <span class="icon">
        <i class="fas fa-save"></i>
    </span>
    <span>Save</span>
</button>

<!-- Secondary Action Button -->
<button type="button" class="button is-light">
    <span class="icon">
        <i class="fas fa-times"></i>
    </span>
    <span>Cancel</span>
</button>

<!-- Small Action Buttons -->
<button class="button is-small is-info edit-booking-btn">
    <span class="icon">
        <i class="fas fa-edit"></i>
    </span>
    <span>Edit</span>
</button>
```

**Icon Standards:**
- ✅ Save: `fa-save`
- ✅ Delete: `fa-trash`
- ✅ Edit: `fa-edit`
- ✅ Add/Create: `fa-plus`
- ✅ Refresh: `fa-sync-alt`
- ✅ Cancel: `fa-times`
- ✅ Clock/Time: `fa-clock`

**Rules:**
- ✅ All action buttons must include icons + text
- ✅ Use consistent icon choices from FontAwesome
- ✅ Structure: `<span class="icon">` + `<span>Text</span>`
- ✅ Apply appropriate Bulma color classes (is-primary, is-danger, etc.)

---

## ⚡ JavaScript Standards

### Security and Data Passing

**Never inject server variables directly into JavaScript:**

```html
<!-- ❌ WRONG - Security vulnerability -->
<script>
    const eventId = {{ selected_event.id }};
</script>

<!-- ✅ CORRECT - Use data attributes -->
<div id="page-data" 
     data-selected-event-id="{{ selected_event.id if selected_event else '' }}"
     data-selected-event-name="{{ selected_event.name if selected_event else '' }}"
     style="display: none;">
</div>

<script>
    const pageData = document.getElementById('page-data');
    const selectedEventId = pageData.dataset.selectedEventId;
    const selectedEventName = pageData.dataset.selectedEventName;
</script>
```

### Modern JavaScript Patterns

**Rules:**
- ✅ Use `const` and `let` exclusively, never `var`
- ✅ Use template literals for string interpolation: `` `Hello ${name}` ``
- ✅ Use data attributes for server-to-client data passing
- ✅ Organize JavaScript in consistent `<script>` blocks at template end
- ✅ Use arrow functions for callbacks when appropriate

### Table Implementation Patterns

**Current Approaches:**
- **Dynamic JavaScript Tables** - Used for search/filter functionality (manage_members.html, members.html)
- **Server-Rendered Tables** - Used for static data with inline editing (manage_events.html bookings)
- **JavaScript-Generated Tables** - Used for complex layouts (bookings_table.html)

**When to Use Each:**
- ✅ **Dynamic JS Tables** - When data needs live search/filtering
- ✅ **Server-Rendered** - When data is mostly static with occasional updates
- ✅ **JS-Generated** - When complex responsive layouts are needed

**Rules:**
- ✅ Maintain consistent styling with Bulma table classes
- ✅ Include proper loading states for dynamic content
- ✅ Use semantic HTML structure regardless of generation method
- ✅ Implement proper error handling for AJAX operations

---

## 🎨 CSS Standards

### Organization and Structure

**No inline styles - use CSS classes:**

```html
<!-- ❌ WRONG -->
<img src="logo.svg" style="max-height: 70px">
<div style="background-color: #f5f5f5;">

<!-- ✅ CORRECT -->
<img src="logo.svg" class="brand-logo">
<div class="booking-form-bg">
```

**CSS Class Organization in custom.css:**

```css
/* Custom utility classes to replace inline styles */
.brand-logo {
  max-height: 70px;
}

.hidden-initially {
  display: none;
}

.booking-form-bg {
  background-color: #f5f5f5;
}

.inline-form {
  display: inline;
}
```

**Rules:**
- ✅ No inline styles in templates
- ✅ Create semantic CSS classes for all styling needs
- ✅ Group related styles with descriptive comments
- ✅ Use Bulma classes first, custom classes for specific needs
- ✅ Maintain consistent naming conventions (kebab-case)

---

## 🗄️ Database Standards

### SQLAlchemy Query Patterns

**Use SQLAlchemy 2.0 syntax exclusively:**

```python
# ✅ CORRECT - Modern SQLAlchemy 2.0
members = db.session.scalars(sa.select(Member).where(
    (Member.username.ilike(f'%{query}%')) |
    (Member.firstname.ilike(f'%{query}%'))
)).all()

# ❌ WRONG - Deprecated syntax
members = Member.query.filter(
    (Member.username.ilike(f'%{query}%'))
).all()
```

### Migration Patterns

**Rules:**
- ✅ Use `server_default='value'` when adding NOT NULL columns to SQLite
- ✅ Specify sensible defaults for new columns
- ✅ Handle existing data gracefully with server defaults
- ✅ Use enumerated fields stored as integers with config mappings

---

## 🔒 Security Standards

### Error Handling Patterns

**Consistent error handling approaches:**

```python
# Web routes - use abort() for HTTP status codes
if not booking:
    abort(404)

if not current_user.is_admin:
    abort(403)

# API endpoints - use try/except with JSON responses
try:
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
except ValueError:
    return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400
```

### Authentication and Authorization

**Rules:**
- ✅ Use `@login_required` for basic authentication
- ✅ Use `@role_required('Role Name')` for role-based access
- ✅ Admin users bypass role checks automatically
- ✅ Consistent 403/404 error responses

---

## 📚 Documentation Standards

### Code Comments

**Rules:**
- ✅ All functions must have docstrings
- ✅ Complex logic sections should have explanatory comments
- ✅ Configuration sections should have descriptive comments
- ✅ Template comments should list which routes use each template

### Configuration Documentation

**Rules:**
- ✅ Document all configuration options in config.py
- ✅ Provide example values and valid ranges
- ✅ Group related configuration items together
- ✅ Use consistent formatting for dictionaries and lists

---

## 🛠️ Development Workflow

### File Organization

**Rules:**
- ✅ Keep routes organized by functionality in routes.py
- ✅ Group related forms in forms.py with consistent validation
- ✅ Utility functions in utils.py with proper documentation
- ✅ Models in models.py with clear relationships

### Testing Patterns

**Rules:**
- ✅ Activate virtual environment before any Flask commands
- ✅ Use Flask test client for route testing
- ✅ Test model functionality and relationships directly
- ✅ Avoid instantiating WTForms outside request context

### Git Practices

**Rules:**
- ✅ Create descriptive commit messages
- ✅ Include generated by Claude Code attribution
- ✅ Group related changes into logical commits
- ✅ Test functionality before committing

---

## 📊 Quality Metrics

### Code Quality Checklist

Before committing code, ensure:
- ✅ All imports are properly organized
- ✅ All functions have appropriate docstrings
- ✅ No inline styles in templates
- ✅ Consistent button patterns with icons
- ✅ Modern SQLAlchemy 2.0 syntax used
- ✅ Secure JavaScript patterns implemented
- ✅ Consistent form layout patterns applied
- ✅ Error handling follows established patterns

### Template Quality Checklist

- ✅ Consistent indentation (4 spaces)
- ✅ Semantic HTML structure
- ✅ Proper Bulma CSS class usage
- ✅ No inline styles
- ✅ Consistent button component patterns
- ✅ Proper form field grouping
- ✅ Secure JavaScript implementation

---

## 🔄 Maintenance

### Regular Review Items

**Monthly:**
- Review and update this style guide
- Check for new inline styles
- Verify SQLAlchemy patterns remain current
- Update JavaScript security patterns

**Per Feature:**
- Apply all style guide rules
- Add appropriate documentation
- Test in development environment
- Review with style guide checklist

---

*This style guide was established during the codebase consistency analysis and improvements performed on 2025-07-08. It should be updated as the project evolves and new patterns emerge.*