#!/usr/bin/env python3
"""
Initial Data Population Script

This script populates the database with essential initial data for a fresh installation.
Run this after creating the database schema with the initial migration.

Usage:
    source venv/bin/activate
    python create_initial_data.py
"""

import os
import sys
from datetime import datetime

# Add the app directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from app.models import Role, Member
from app.audit import audit_log_create, audit_log_system_event
from config import Config
from werkzeug.security import generate_password_hash


def create_initial_roles():
    """Create the standard roles for the bowls club."""
    roles_to_create = Config.STANDARD_ROLES
    
    print("Creating initial roles...")
    created_count = 0
    
    for role_name in roles_to_create:
        # Check if role already exists
        existing_role = db.session.query(Role).filter_by(name=role_name).first()
        if not existing_role:
            role = Role(name=role_name)
            db.session.add(role)
            created_count += 1
            print(f"  - Created role: {role_name}")
        else:
            print(f"  - Role already exists: {role_name}")
    
    db.session.commit()
    
    # Audit log the system initialization
    if created_count > 0:
        audit_log_system_event('INITIALIZATION', 
                              f'System initialization: Created {created_count} initial roles',
                              {'roles_created': created_count})
    print(f"Roles created: {created_count}")
    return created_count


def check_bootstrap_mode():
    """Check if the system is in bootstrap mode (no users exist)."""
    user_count = db.session.query(Member).count()
    is_bootstrap = user_count == 0
    
    print(f"\nBootstrap mode check:")
    print(f"  - Users in database: {user_count}")
    print(f"  - Bootstrap mode: {'Yes' if is_bootstrap else 'No'}")
    
    if is_bootstrap:
        print(f"  - First user registration will automatically become admin")
        print(f"  - Visit the registration page to create the first admin user")
    
    return is_bootstrap


def verify_database_structure():
    """Verify that all expected tables exist."""
    print("\nVerifying database structure...")
    
    expected_tables = [
        'roles', 'member', 'member_roles', 'events', 'event_member_managers',
        'posts', 'policy_pages', 'bookings', 'event_teams', 'booking_teams',
        'team_members', 'booking_team_members'
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
        print(f"\nERROR: Missing tables: {missing_tables}")
        print("Please run the database migration first:")
        print("  flask db upgrade")
        return False
    
    print("Database structure verification complete!")
    return True


def main():
    """Main function to set up initial data."""
    print("=" * 60)
    print("BOWLS CLUB - Initial Data Setup")
    print("=" * 60)
    
    with app.app_context():
        # Verify database structure
        if not verify_database_structure():
            sys.exit(1)
        
        # Create roles
        roles_created = create_initial_roles()
        
        # Check bootstrap mode (instead of creating admin user)
        is_bootstrap = check_bootstrap_mode()
        
        print("\n" + "=" * 60)
        print("SETUP COMPLETE!")
        print("=" * 60)
        print(f"Roles created: {roles_created}")
        print(f"Bootstrap mode: {'Yes' if is_bootstrap else 'No'}")
        
        if is_bootstrap:
            print("\nIMPORTANT NEXT STEPS:")
            print("1. Start the Flask application (flask run)")
            print("2. Visit the registration page (/add_member)")
            print("3. Create the first user - they will automatically become admin")
            print("4. Create additional members through the web interface")
            print("5. Assign appropriate roles to members")
        else:
            print("\nSYSTEM READY:")
            print("- Users already exist in the system")
            print("- No bootstrap needed")
        
        print("\nYour bowls club application is ready to use!")


if __name__ == '__main__':
    main()