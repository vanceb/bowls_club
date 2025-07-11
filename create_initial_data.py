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
from werkzeug.security import generate_password_hash


def create_initial_roles():
    """Create the standard roles for the bowls club."""
    roles_to_create = [
        'Event Manager',
        'Secretary', 
        'Treasurer',
        'Captain',
        'Vice Captain',
        'Committee Member',
        'Social Committee',
        'Greens Keeper',
        'Match Secretary'
    ]
    
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
    print(f"Roles created: {created_count}")
    return created_count


def create_admin_user():
    """Create an initial admin user."""
    print("\nCreating initial admin user...")
    
    # Check if admin user already exists
    admin_user = db.session.query(Member).filter_by(username='admin').first()
    if admin_user:
        print("  - Admin user already exists")
        return False
    
    # Create admin user
    admin = Member(
        username='admin',
        email='admin@bowlsclub.local',
        phone='000-000-0000',  # Default admin phone
        firstname='Admin',
        lastname='User',
        password_hash=generate_password_hash('admin123'),  # Change this in production!
        is_admin=True,
        gender='Other',
        status='Full',
        share_email=False,
        share_phone=False
    )
    
    db.session.add(admin)
    db.session.commit()
    
    print("  - Created admin user")
    print("    Username: admin")
    print("    Password: admin123")
    print("    WARNING: Change the admin password immediately!")
    
    return True


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
        
        # Create admin user
        admin_created = create_admin_user()
        
        print("\n" + "=" * 60)
        print("SETUP COMPLETE!")
        print("=" * 60)
        print(f"Roles created: {roles_created}")
        print(f"Admin user created: {'Yes' if admin_created else 'Already exists'}")
        
        if admin_created:
            print("\nIMPORTANT NEXT STEPS:")
            print("1. Log in as admin (username: admin, password: admin123)")
            print("2. Change the admin password immediately")
            print("3. Create additional members through the web interface")
            print("4. Assign appropriate roles to members")
        
        print("\nYour bowls club application is ready to use!")


if __name__ == '__main__':
    main()