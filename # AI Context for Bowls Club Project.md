# AI Context for Bowls Club Project

## Overview
This project is a Flask-based web application designed for managing a bowls club. It includes features for member management, role-based access control, and administrative tools.

## Technologies and Libraries Used
### Backend
- **Flask**: A lightweight WSGI web application framework.
- **Flask-SQLAlchemy**: An ORM for managing database interactions.
- **Flask-Migrate**: For handling database migrations using Alembic.
- **Flask-Login**: For user session management and authentication.
- **Flask-WTF**: For form handling and CSRF protection.
- **SQLAlchemy**: For database modeling and querying.
- **Werkzeug**: For password hashing and security utilities.

### Frontend
- **Bulma**: A CSS framework for styling and responsive design.
- **Jinja2**: For server-side templating.

### Email
- **Flask-Mail**: For sending emails (e.g., password reset requests).

### Database
- **SQLite**: Used as the default database for development.

### Other Tools
- **Alembic**: For database schema migrations.
- **itsdangerous**: For generating and verifying secure tokens (e.g., password reset tokens).

## Project Structure
- **`app/`**: Contains the main application code.
  - **`__init__.py`**: Initializes the Flask app and extensions.
  - **`models.py`**: Defines the database models (e.g., `Member`, `Role`).
  - **`routes.py`**: Contains the route handlers for the application.
  - **`forms.py`**: Defines the forms used in the application.
  - **`utils.py`**: Utility functions (e.g., email sending, token generation).
  - **`templates/`**: Jinja2 templates for rendering HTML pages.
  - **`static/`**: Static files like CSS and images.
- **`migrations/`**: Contains Alembic migration scripts.
- **`config.py`**: Configuration settings for the application.
- **`bowls.py`**: The main entry point for running the application.

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
   - Flask-Migrate is the wrapper around Alembic

## Configuration
- Environment variables are used for sensitive settings like `SECRET_KEY`, `MAIL_SERVER`, and `DATABASE_URL`.
- Default database: SQLite (`app.db`).
- Default email settings are configured in `config.py`.

## Notes
- The project includes a `MENU_ITEMS` structure in `config.py` for dynamically generating navigation menus.
- Admin-specific features are accessible via the "Admin" dropdown in the navigation bar.

## Future Enhancements
- Add unit tests for critical functionality.
- Implement additional role-based permissions.
- Enhance the UI with more interactive elements.

## AI Interaction
- When considering your answer you should aim to reuse the technologies and coding style contained in the project
- Changes to the code should take a fine-grained approach changing individual lines rather then replacing large block of code where possible
- When creating new functions you should provide a multi-line comment describing the purpose of the function, its inputs and outputs and any potential errors
- html templates should contain a comment listing the routes which use that template