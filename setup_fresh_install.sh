#!/bin/bash

# Fresh Installation Setup Script for Bowls Club Application
# This script automates the complete setup process for a fresh installation

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

# Step 2: Run database migration
echo "🔧 Creating database schema..."
flask db upgrade
echo "✓ Database schema created"

# Step 3: Populate initial data
echo "🔧 Populating initial data..."
python create_initial_data.py
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
echo "Bootstrap Mode Configuration:"
echo "  - No initial admin user is created by this script"
echo "  - The first user you register will automatically become admin"
echo "  - Visit /add_member to create the first admin user"
echo ""
echo "⚠️  IMPORTANT: The first user registration automatically gets admin privileges!"
echo ""
echo "Next steps:"
echo "  1. Start the application with 'flask run'"
echo "  2. Open http://localhost:5000 in your browser"
echo "  3. Register the first admin user at /add_member"
echo "  4. Create additional member accounts for your club"
echo "  5. Assign roles to members as needed"
echo "  6. Configure events and teams for your club"
echo ""
echo "For detailed instructions, see FRESH_INSTALL.md"
echo ""