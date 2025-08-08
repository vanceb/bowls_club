#!/bin/bash

# Fresh Installation Setup Script for Bowls Club Application
# This script automates the complete setup process for a fresh installation
# Updated for booking-centric architecture with pool strategy support

set -e  # Exit on any error

echo "============================================================"
echo "BOWLS CLUB - FRESH INSTALLATION SETUP"
echo "============================================================"

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "ERROR: Virtual environment is not activated!"
    echo "Please run: source venv/bin/activate"
    exit 1
fi

echo "✓ Virtual environment is activated"

# Check if Flask is available
if ! command -v flask &> /dev/null; then
    echo "ERROR: Flask command not found!"
    echo "Please ensure Flask is installed in your virtual environment"
    exit 1
fi

echo "✓ Flask is available"

# Check if we're in the correct directory
if [[ ! -f "bowls.py" ]] || [[ ! -f "config.py" ]]; then
    echo "ERROR: Not in the correct directory!"
    echo "Please run this script from the root of the bowls club application"
    exit 1
fi

echo "✓ In correct application directory"

# Backup existing database if it exists
if [[ -f "instance/app.db" ]]; then
    echo "⚠️  Existing database found!"
    read -p "Do you want to backup the existing database? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        timestamp=$(date +"%Y%m%d_%H%M%S")
        cp instance/app.db "instance/app.db.backup_$timestamp"
        echo "✓ Database backed up to instance/app.db.backup_$timestamp"
    fi
    
    read -p "Do you want to proceed with fresh installation? This will DELETE existing data! (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
    
    echo "Removing existing database..."
    rm instance/app.db
fi

# Create instance directory if it doesn't exist
mkdir -p instance

echo ""
echo "Starting fresh installation..."
echo ""

# Step 1: Initialize database migrations (if not already done)
if [[ ! -d "migrations" ]]; then
    echo "🔧 Initializing database migrations..."
    flask db init
    echo "✓ Database migrations initialized"
else
    echo "✓ Database migrations already initialized"
fi

# Step 2: Handle database migration state
echo "🔧 Setting up database schema..."

# If we just deleted the database, we need to create it from scratch
# First try to upgrade normally, if that fails, reset the migration state
if ! flask db upgrade 2>/dev/null; then
    echo "🔧 Database not in sync with migrations, resetting migration state..."
    # Create the database file first
    touch instance/app.db
    # Reset migration state to current migration
    flask db stamp head
    echo "✓ Migration state reset"
    
    # Now upgrade should work
    flask db upgrade
fi

echo "✓ Database schema created"

# Step 4: Populate initial data
echo "🔧 Populating initial data..."
python bin/create_initial_data.py
echo "✓ Initial data populated"

echo ""
echo "============================================================"
echo "INSTALLATION COMPLETE!"
echo "============================================================"
echo ""
echo "Your Bowls Club application is ready to use!"
echo ""
echo "To start the application:"
echo "  flask run"
echo ""
echo "Initial Setup Complete:"
echo "  - Database schema created with booking-centric architecture"
echo "  - Pool strategy system enabled (EVENT_POOL_STRATEGY configuration)"
echo "  - Core roles established (User Manager, Content Manager, Event Manager)" 
echo "  - First admin user created during setup"
echo ""
echo "Next steps:"
echo "  1. Start the application with 'flask run'"
echo "  2. Open http://localhost:5000 in your browser"
echo "  3. Log in using the admin credentials you just created"
echo "  4. Create additional member accounts for your club"
echo "  5. Assign roles to members as needed"
echo "  6. Create bookings for your club's games and events"
echo "  7. Use pools for member registration (based on EVENT_POOL_STRATEGY)"
echo "  8. Set up teams for individual games as needed"
echo ""
echo "For detailed instructions, see FRESH_INSTALL.md"
echo ""