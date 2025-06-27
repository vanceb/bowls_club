# Bowls Club Project – AI & Claude Context

## Overview

This project is a Flask-based web application designed for managing a bowls club. It includes features for member management, role-based access control, bookings, posts, and administrative tools.

---

## Technologies and Libraries Used

### Backend
- **Flask**: Lightweight WSGI web application framework.
- **Flask-SQLAlchemy**: ORM for managing database interactions.
- **Flask-Migrate**: Handles database migrations using Alembic.
- **Flask-Login**: User session management and authentication.
- **Flask-WTF**: Form handling and CSRF protection.
- **SQLAlchemy**: Database modeling and querying.
- **Werkzeug**: Password hashing and security utilities.

### Frontend
- **Bulma**: CSS framework for styling and responsive design.
- **Jinja2**: Server-side templating.

### Email
- **Flask-Mail**: For sending emails (e.g., password reset requests).

### Database
- **SQLite**: Default database for development.

### Other Tools
- **Alembic**: For database schema migrations.
- **itsdangerous**: For generating and verifying secure tokens (e.g., password reset tokens).

---

## Project Structure

- **`app/`**: Main application code.
  - **`__init__.py`**: Initializes the Flask app and extensions.
  - **`models.py`**: Database models (e.g., `Member`, `Role`, `Booking`).
  - **`routes.py`**: Route handlers for the application.
  - **`forms.py`**: WTForms forms.
  - **`utils.py`**: Utility functions (e.g., email sending, token generation).
  - **`templates/`**: Jinja2 templates for rendering HTML pages. All templates should extend `base.html`.
  - **`static/`**: Static files like CSS and images.
- **`migrations/`**: Alembic migration scripts.
- **`config.py`**: Configuration settings for the application.
- **`bowls.py`**: Main entry point for running the application.

---

## Key Features

1. **Member Management**:
   - Add, edit, and delete members.
   - Search members by name or email.
   - Assign roles to members.

2. **Role-Based Access Control**:
   - Admin users can manage roles and permissions.
   - Protect routes using the `@admin_required` decorator.

3. **Authentication**:
   - Login and logout functionality.
   - Password reset via email.

4. **Error Handling**:
   - Custom error pages for 403, 404, and 500 errors.

5. **Responsive Design**:
   - Uses Bulma for a mobile-friendly UI.

6. **Database Migrations**:
   - Alembic is used to manage schema changes.
   - Flask-Migrate is the wrapper around Alembic.

7. **Bookings Table**:
   - Dynamically generated for a selected date.
   - Columns = rinks (1 to `RINKS` from config).
   - Rows = sessions (from `DAILY_SESSIONS` in config).
   - Booked cells have the `booked` class and are styled via CSS (default: red background).

---

## Configuration

- Environment variables are used for sensitive settings like `SECRET_KEY`, `MAIL_SERVER`, and `DATABASE_URL`.
- Default database: SQLite (`app.db`).
- Default email settings are configured in `config.py`.
- `MENU_ITEMS` structure in `config.py` for dynamically generating navigation menus.
- Admin-specific features are accessible via the "Admin" dropdown in the navigation bar.
- Use configuration values from `config.py` for anything that may change (e.g., number of rinks, session times).

---

## Favicons

- Place favicon files in `app/static/images/`.
- Use at least `favicon-16x16.png` and `favicon-32x32.png`.
- Reference them in `base.html` using Flask's `url_for('static', ...)`.
- Example:
  ```html
  <link rel="icon" type="image/png" sizes="32x32" href="{{ url_for('static', filename='images/favicon-32x32.png') }}">
  <link rel="icon" type="image/png" sizes="16x16" href="{{ url_for('static', filename='images/favicon-16x16.png') }}">
  ```

---

## Customization

- To override Bulma styles, use more specific selectors or `!important` in `custom.css`.
- For link colors, override `a`, `.navbar-item`, and `.has-text-link` as needed.
- All forms use WTForms and are styled with Bulma classes.
- All pages should use Jinja2 template inheritance and extend `base.html`.

---

## Example Directory Structure

```
app/
  static/
    css/custom.css
    images/favicon-16x16.png
    images/favicon-32x32.png
    images/apple-touch-icon.png
    images/site.webmanifest
  templates/
    base.html
    bookings_table.html
    booking_form.html
    ...
  models.py
  routes.py
  forms.py
config.py
```

---

## General Guidance

- Always use Jinja2 template inheritance for new pages.
- Use Flask's `url_for` for all static and route links.
- Keep code changes minimal and non-breaking.
- Use Bulma classes for layout and form styling, and extend with custom CSS as needed.
- When creating new functions, provide a multi-line comment describing the purpose, inputs, outputs, and potential errors.
- HTML templates should contain a comment listing the routes which use that template.

---

## Future Enhancements

- Add unit tests for critical functionality.
- Implement additional role-based permissions.
- Enhance the UI with more interactive elements.

---

## AI Interaction

- When considering your answer you should aim to reuse the technologies and coding style contained in the project.
- Changes to the code should take a fine-grained approach, changing individual lines rather than replacing large blocks of code where possible.
- When creating new functions, provide a multi-line comment describing the purpose of the function, its inputs and outputs, and any potential errors.
- HTML templates should contain a comment listing the routes which use that template.

---

This file is intended to provide context for AI assistants and developers to ensure consistency and best practices across the Bowls Club