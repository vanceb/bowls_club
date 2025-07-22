#!/usr/bin/env python3
"""
Fresh Install Validation Script

This script validates that a fresh installation was completed successfully.
Run this after running the fresh install process.

Usage:
    source venv/bin/activate
    python validate_fresh_install.py
"""

import os
import sys
from datetime import datetime

# Add the app directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .flaskenv if available
try:
    from dotenv import load_dotenv
    load_dotenv('.flaskenv')
except ImportError:
    pass

from app import create_app, db
from app.models import Role, Member

def validate_database_structure():
    """Validate that all expected tables exist and have correct structure."""
    print("🔍 Validating database structure...")
    
    expected_tables = [
        'roles', 'member', 'member_roles', 'events', 'event_member_managers',
        'event_pools', 'pool_members', 'posts', 'policy_pages', 'bookings', 
        'event_teams', 'booking_teams', 'team_members', 'booking_team_members',
        'booking_players'
    ]
    
    # Get all table names from the database
    inspector = db.inspect(db.engine)
    existing_tables = inspector.get_table_names()
    
    missing_tables = []
    for table in expected_tables:
        if table in existing_tables:
            print(f"  ✓ Table '{table}' exists")
        else:
            print(f"  ✗ Table '{table}' missing")
            missing_tables.append(table)
    
    if missing_tables:
        print(f"\n❌ VALIDATION FAILED: Missing tables: {missing_tables}")
        return False
    
    print("✅ Database structure validation passed!")
    return True

def validate_initial_data():
    """Validate that initial data was created correctly."""
    print("\n🔍 Validating initial data...")
    
    # Check roles
    role_count = db.session.query(Role).count()
    print(f"  📊 Found {role_count} roles in database")
    
    if role_count < 3:
        print("  ❌ Expected at least 3 core roles")
        return False
    
    # Check for core roles
    core_roles = ['User Manager', 'Content Manager', 'Event Manager']
    for role_name in core_roles:
        role = db.session.query(Role).filter_by(name=role_name).first()
        if role:
            print(f"  ✓ Core role '{role_name}' exists")
        else:
            print(f"  ✗ Core role '{role_name}' missing")
            return False
    
    # Check bootstrap mode
    user_count = db.session.query(Member).count()
    print(f"  👥 Found {user_count} users in database")
    
    if user_count == 0:
        print("  ✓ Bootstrap mode: System ready for first user registration")
    else:
        print(f"  ℹ️  System has {user_count} existing users")
    
    print("✅ Initial data validation passed!")
    return True

def validate_migration_status():
    """Validate that migration is at correct state."""
    print("\n🔍 Validating migration status...")
    
    try:
        # Check current migration revision
        from flask_migrate import current
        with app.app_context():
            current_rev = current()
            print(f"  📋 Current migration revision: {current_rev}")
            
            if current_rev is None:
                print("  ❌ No migration applied")
                return False
            
            if current_rev == '88670c18718b':
                print("  ✅ Correct consolidated migration applied")
                return True
            else:
                print(f"  ⚠️  Unexpected migration revision: {current_rev}")
                return False
                
    except Exception as e:
        print(f"  ❌ Error checking migration status: {e}")
        return False

def main():
    """Main validation function."""
    print("=" * 60)
    print("BOWLS CLUB - FRESH INSTALL VALIDATION")
    print("=" * 60)
    
    # Create app instance
    global app
    app = create_app()
    
    with app.app_context():
        # Run all validations
        validations = [
            validate_database_structure(),
            validate_initial_data(), 
            validate_migration_status()
        ]
        
        print("\n" + "=" * 60)
        if all(validations):
            print("🎉 ALL VALIDATIONS PASSED!")
            print("=" * 60)
            print("✅ Your fresh installation is complete and ready to use!")
            print()
            print("Next steps:")
            print("  1. Start the application: flask run")
            print("  2. Open http://localhost:5000")
            print("  3. Register first admin user at /add_member") 
            print("  4. Begin configuring your bowls club!")
        else:
            print("❌ VALIDATION FAILED!")
            print("=" * 60)
            print("Please check the errors above and re-run the fresh install process.")
            sys.exit(1)

if __name__ == '__main__':
    main()