# Fresh Installation Guide

This guide explains how to set up a completely fresh installation of the Bowls Club application with the consolidated database schema.

## Prerequisites

- Python 3.8+
- Virtual environment set up
- Flask and all dependencies installed

## Fresh Installation Steps

### 1. Activate Virtual Environment
```bash
source venv/bin/activate
```

### 2. Initialize Database (if not already done)
```bash
flask db init
```

### 3. Create Database Schema
```bash
flask db upgrade
```

This will run the consolidated migration that creates all tables in their current state.

### 4. Populate Initial Data
```bash
python create_initial_data.py
```

This script will:
- Create standard roles (Event Manager, Secretary, Treasurer, etc.)
- Create an initial admin user
- Verify the database structure

### 5. Start the Application
```bash
flask run
```

### 6. Initial Login
- **Username:** `admin`
- **Password:** `admin123`
- **⚠️ IMPORTANT:** Change the admin password immediately after first login!

## What Gets Created

### Database Tables
- `roles` - User roles (Event Manager, Secretary, etc.)
- `member` - Club members with authentication
- `member_roles` - Many-to-many relationship for member roles
- `events` - Event types and definitions
- `event_member_managers` - Event managers assignment
- `posts` - News/announcements system
- `policy_pages` - Static pages (privacy policy, terms, etc.)
- `bookings` - Facility bookings with date/time/rinks
- `event_teams` - Template teams for events
- `booking_teams` - Actual teams for specific bookings
- `team_members` - Players assigned to event teams
- `booking_team_members` - Player availability for specific games

### Initial Roles Created
- Event Manager
- Secretary
- Treasurer
- Captain
- Vice Captain
- Committee Member
- Social Committee
- Greens Keeper
- Match Secretary

### Features Available
- ✅ Member management with role-based permissions
- ✅ Event creation and team management
- ✅ Booking system with rink availability
- ✅ Team formation with position assignments
- ✅ Player availability confirmation system
- ✅ Substitution management
- ✅ News/announcements system
- ✅ Static page management
- ✅ Home/away game tracking
- ✅ Opposition team management

## Configuration

### Environment Variables
Set these in your environment or `.env` file:
- `SECRET_KEY` - Flask secret key for sessions
- `DATABASE_URL` - Database connection string (optional, defaults to SQLite)
- `MAIL_SERVER` - Email server for notifications (optional)

### Application Settings
Edit `config.py` to customize:
- `RINKS` - Number of available rinks (default: 6)
- `DAILY_SESSIONS` - Time slots available for booking
- `EVENT_TYPES` - Types of events (Pennant, Social, etc.)
- `TEAM_POSITIONS` - Player positions for different game formats

## Troubleshooting

### Migration Issues
If you encounter migration issues:
```bash
# Remove any existing database
rm instance/app.db

# Recreate from scratch
flask db upgrade
python create_initial_data.py
```

### Admin User Issues
If the admin user doesn't work:
```bash
# Run the data population script again
python create_initial_data.py
```

### Permission Issues
- Ensure all users have appropriate roles assigned
- Event Managers can create events and manage teams
- Regular members can view their assignments and confirm availability

## Migration from Old Database

If you have an existing database with the old migration history:

### Option 1: Fresh Start (Recommended for Development)
```bash
# Backup existing data if needed
cp instance/app.db instance/app.db.backup

# Remove old database
rm instance/app.db

# Create fresh database
flask db upgrade
python create_initial_data.py
```

### Option 2: Stamp Existing Database
```bash
# Mark current database as being at the new baseline
flask db stamp bbec59aa9936

# Note: This assumes your current database matches the consolidated schema
```

## Next Steps After Installation

1. **Change Admin Password**
   - Log in as admin
   - Go to Profile → Edit Profile
   - Change password to something secure

2. **Create Members**
   - Use Admin → Manage Members
   - Create member accounts for your club

3. **Assign Roles**
   - Edit members to assign appropriate roles
   - Event Managers can create and manage events

4. **Configure Events**
   - Create your regular events (Pennant, Social games, etc.)
   - Set up teams for each event type

5. **Customize Settings**
   - Edit `config.py` for your club's specific needs
   - Update daily sessions, rink count, etc.

The application is now ready for production use with all features available!