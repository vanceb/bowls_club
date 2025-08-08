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
from datetime import datetime, date

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .flaskenv if available
try:
    from dotenv import load_dotenv
    load_dotenv('.flaskenv')
except ImportError:
    pass

from app import create_app, db
from app.models import Role, Member
from config import Config
from werkzeug.security import generate_password_hash


def create_initial_roles():
    """Create the core roles for the bowls club."""
    roles_to_create = Config.CORE_ROLES
    
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
    """Create the first admin user interactively."""
    user_count = db.session.query(Member).count()
    
    if user_count > 0:
        print(f"\nUsers already exist in database ({user_count} users)")
        print("Skipping admin user creation")
        return False
    
    print(f"\n" + "="*50)
    print("CREATE FIRST ADMIN USER")
    print("="*50)
    print("No users exist in the database. Let's create the first admin user.")
    print("This user will have full administrative privileges.")
    print()
    
    # Get user details interactively
    while True:
        username = input("Username: ").strip()
        if username:
            # Check if username already exists (shouldn't happen but be safe)
            existing = db.session.query(Member).filter_by(username=username).first()
            if not existing:
                break
            print("Username already exists. Please choose another.")
        else:
            print("Username cannot be empty.")
    
    while True:
        firstname = input("First Name: ").strip()
        if firstname:
            break
        print("First name cannot be empty.")
    
    while True:
        lastname = input("Last Name: ").strip()
        if lastname:
            break
        print("Last name cannot be empty.")
    
    while True:
        email = input("Email: ").strip()
        if email and '@' in email:
            break
        print("Please enter a valid email address.")
    
    phone = input("Phone (optional): ").strip()
    
    # Get password securely
    import getpass
    while True:
        password = getpass.getpass("Password: ")
        if len(password) >= 6:
            password_confirm = getpass.getpass("Confirm Password: ")
            if password == password_confirm:
                break
            else:
                print("Passwords don't match. Please try again.")
        else:
            print("Password must be at least 6 characters long.")
    
    # Create the admin user
    admin_user = Member(
        username=username,
        firstname=firstname,
        lastname=lastname,
        email=email,
        phone=phone,
        status='Full',  # Full member status
        is_admin=True,  # Admin privileges
        joined_date=date.today(),  # Required field
        share_email=True,
        share_phone=bool(phone)
    )
    
    admin_user.set_password(password)
    
    db.session.add(admin_user)
    db.session.commit()
    
    print(f"\n✓ Admin user '{username}' created successfully!")
    print(f"✓ Status: Full")
    print(f"✓ Admin privileges: Yes")
    print(f"✓ You can now log in with these credentials")
    
    return True


def verify_database_structure():
    """Verify that all expected tables exist."""
    print("\nVerifying database structure...")
    
    expected_tables = [
        'roles', 'member', 'member_roles', 'booking_member_managers',
        'pools', 'pool_registrations', 'posts', 'policy_pages', 'bookings',
        'teams', 'team_members'
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
    
    # Create app instance
    app = create_app()
    
    with app.app_context():
        # Verify database structure
        if not verify_database_structure():
            sys.exit(1)
        
        # Create roles
        roles_created = create_initial_roles()
        
        # Create admin user if no users exist
        admin_created = create_admin_user()
        
        print("\n" + "=" * 60)
        print("SETUP COMPLETE!")
        print("=" * 60)
        print(f"Roles created: {roles_created}")
        print(f"Admin user created: {'Yes' if admin_created else 'No'}")
        
        if admin_created:
            print("\nSYSTEM READY FOR USE:")
            print("1. Start the Flask application:")
            print("   source venv/bin/activate")
            print("   flask run")
            print("2. Log in using the admin credentials you just created")
            print("3. Create additional members through the admin interface")
            print("4. Assign appropriate roles to members as needed")
            print("5. The /members/apply route is now for public member applications")
        else:
            print("\nSYSTEM READY:")
            print("- Users already exist in the system")
            print("- Admin user already configured")
        
        print("\nYour bowls club application is ready to use!")


if __name__ == '__main__':
    main()