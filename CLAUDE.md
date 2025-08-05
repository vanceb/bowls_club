# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentation Structure

This project uses hierarchical CLAUDE.md files for specific areas:

- **`CLAUDE.md`** (this file) - Project overview, environment setup, and Git workflow
- **`app/CLAUDE.md`** - Flask application development guidelines including blueprints, security, and patterns
- **`app/templates/CLAUDE.md`** - HTML template and frontend development guidelines

Always check the appropriate file for specific guidance on the area you're working in.

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

### Running a Test/Debug Server
**For testing and debugging purposes, especially when port 5000 is in use:**

```bash
# ALWAYS activate virtual environment first
source venv/bin/activate

# Use Flask with custom port
flask run --port 5001
```

**Important Notes:**
- The `.flaskenv` file contains the SECRET_KEY and other environment variables
- If you get "SECRET_KEY environment variable is required", either:
  - Ensure `.flaskenv` exists and contains `SECRET_KEY=your-key-here`
  - Or export the SECRET_KEY manually
- The server will show a warning about in-memory rate limiting storage - this is normal for development

## Access Flask shell with pre-loaded Flask context
```bash
flask shell
```

### Database Operations
```bash
# Create database migration
flask db migrate -m "description of changes"
```

**Important** If this is a complex migration then you may need to edit the migration script

```bash
# Apply database migrations
flask db upgrade
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

## Testing Guidelines

**IMPORTANT: When testing Flask forms programmatically, avoid CSRF failures:**

- **DO NOT** instantiate WTForms directly in test scripts (EventForm(), BookingForm(), etc.)
- Forms use Flask-WTF with CSRF protection that requires HTTP request context
- **Instead, test the underlying models and database operations**
- **For route testing:** Use Flask's test client or run the development server
- **For form testing:** Test via HTTP requests, not direct instantiation

*See `app/CLAUDE.md` for detailed testing examples and guidelines.*

## Security Guidelines

### Security Guidelines

**CRITICAL Security Requirements:**
- All Flask-specific security patterns are detailed in `app/CLAUDE.md`
- CSRF protection, audit logging, and authentication patterns
- Never expose or log secrets and keys
- Never commit secrets or keys to the repository

### General Security Notes

**CRITICAL** 
- Always follow security best practices
- Never introduce code that exposes or logs secrets and keys
- Never commit secrets or keys to the repository
- All database changes must include audit logging
- Use appropriate audit logging functions for all operations

## Code Style Guidelines

**IMPORTANT: DO NOT ADD ANY COMMENTS unless asked**

- Follow existing code conventions and patterns in `app/CLAUDE.md`
- See detailed style guidelines in `app/CLAUDE.md` for Flask-specific patterns
- See `app/templates/CLAUDE.md` for frontend and template guidelines

## Code Reuse and Minimalism

**CRITICAL: Prioritize code reuse and minimize new code creation**

### 1. Keep Additional Code Minimal
- **Wherever possible, reuse existing code, functions, forms, and templates**
- Before creating new functions, check if existing utilities can be extended or reused
- Before creating new forms, check if existing forms can be modified or extended
- Before creating new templates, check if existing templates or partials can be reused
- Prefer extending existing classes over creating new ones
- Prefer adding parameters to existing functions over creating duplicate functions

### 2. **NEVER** Remove or Break Existing Functionality
- **CRITICAL**: Do not remove existing routes, functions, or features
- **CRITICAL**: Do not modify existing function signatures that would break calling code
- **CRITICAL**: Do not change existing database models in ways that break existing data
- When fixing bugs, ensure the fix doesn't break other functionality that depends on the current behavior
- When adding features, ensure they don't interfere with existing workflows
- Always test that existing functionality still works after your changes

### Examples of Good Practice:
- **✅ Extend existing forms**: Add new fields to existing forms rather than creating duplicate forms
- **✅ Reuse existing templates**: Use existing templates with conditional sections rather than creating new ones
- **✅ Extend existing routes**: Add optional parameters to existing routes rather than creating new endpoints
- **✅ Reuse existing utilities**: Extend existing utility functions rather than creating similar new ones
- **✅ Preserve existing APIs**: When modifying functions, maintain backward compatibility

### Examples of Bad Practice:
- **❌ Create duplicate forms**: Creating `NewPasswordForm` when `PasswordChangeForm` already exists
- **❌ Remove working code**: Deleting existing functions or routes that other code depends on
- **❌ Break existing signatures**: Changing function parameters without checking all callers
- **❌ Create redundant templates**: Building new templates when existing ones could be extended
- **❌ Ignore existing patterns**: Using different coding patterns instead of following established conventions

## Git Workflow - GitHub Flow

**CRITICAL: This repository uses GitHub Flow. ALL changes must go through feature branches and Pull Requests.**

### Starting New Work
```bash
# ALWAYS start from main
git checkout main
git pull origin main

# Create feature branch with descriptive name
git checkout -b feature/your-feature-name
# OR for bug fixes
git checkout -b fix/bug-description
# OR for enhancements
git checkout -b enhancement/improvement-name
```

### Working on Features
```bash
# Make changes, then stage and commit frequently
git add .
git commit -m "Descriptive commit message explaining what and why"

# Push to remote (first time)
git push -u origin feature/your-feature-name

# Subsequent pushes
git push
```

### Completing Work
```bash
# Push final changes
git push

# Create Pull Request on GitHub:
# 1. Go to https://github.com/vanceb/bowls_club
# 2. Click "Pull requests" → "New pull request"
# 3. Select your feature branch
# 4. Add description and create PR

# After PR is merged, clean up:
git checkout main
git pull origin main
git branch -d feature/your-feature-name
```

### Branch Naming Convention
- **feature/**: New functionality (`feature/roll-up-booking`, `feature/member-search`)
- **fix/**: Bug fixes (`fix/login-error`, `fix/booking-validation`)
- **enhancement/**: Improvements (`enhancement/ui-improvements`, `enhancement/performance`)

### Git Workflow Rules
1. **NEVER commit directly to main** - Always use feature branches
2. **Keep branches small and focused** - One feature per branch
3. **Use descriptive commit messages** - Explain what and why
4. **Create PRs for ALL changes** - Even small fixes need review
5. **Delete branches after merging** - Keep repository clean
6. **Pull main frequently** - Keep feature branches up to date

### Before Starting Any Work
```bash
# Check you're on main and up to date
git status
git checkout main
git pull origin main

# Only then create your feature branch
git checkout -b feature/your-new-feature
```

**IMPORTANT: If you find yourself working directly on main, immediately:**
1. Create a feature branch: `git checkout -b feature/emergency-fix`
2. Continue your work on the feature branch
3. Follow the PR process before merging

## Architecture Overview

- Flask web application with Blueprint architecture (see `app/CLAUDE.md`)
- SQLAlchemy ORM with audit logging
- Bulma CSS framework for UI (see `app/templates/CLAUDE.md`)
- Role-based access control system
- Event and booking management with team assignments
- File-based content management for posts and policies
- `migrations/CLAUDE.md` - Database migration procedures

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.