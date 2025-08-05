#!/usr/bin/env python3
"""
Create Admin User Script

Creates a specific admin user for bootstrap purposes.
Run this after the database has been created and initial data populated.

Usage:
    source venv/bin/activate
    python create_admin_user.py
"""

import os
import sys

# Add the app directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .flaskenv if available
try:
    from dotenv import load_dotenv
    load_dotenv('.flaskenv')
except ImportError:
    pass

from app import create_app, db
from app.models import Member
from app.audit import audit_log_system_event

def create_admin_user():
    """Create the admin user with specific credentials."""
    app = create_app()
    
    with app.app_context():
        # Check if any users exist
        user_count = db.session.query(Member).count()
        
        if user_count > 0:
            print(f"Users already exist in database ({user_count} users)")
            print("Admin user creation skipped")
            return False
        
        print("Creating admin user...")
        
        # Create the admin user
        admin_user = Member(
            username='admin',
            firstname='Admin',
            lastname='User',
            email='admin@bowlsclub.local',
            phone='',
            status='Full',  # Full member status
            is_admin=True,  # Admin privileges
            share_email=True,
            share_phone=False
        )
        
        # Set a default password (should be changed after first login)
        admin_user.set_password('admin123')
        
        db.session.add(admin_user)
        db.session.commit()
        
        # Audit log
        audit_log_system_event('BOOTSTRAP_ADMIN_CREATED', 
                             f'Bootstrap admin user created: {admin_user.firstname} {admin_user.lastname} ({admin_user.username})',
                             {
                                 'user_id': admin_user.id,
                                 'username': admin_user.username,
                                 'status': 'Full',
                                 'is_admin': True,
                                 'bootstrap_user': True
                             })
        
        print(f"✓ Admin user 'admin' created successfully!")
        print(f"✓ Username: admin")
        print(f"✓ Password: admin123")
        print(f"✓ Status: Full")
        print(f"✓ Admin privileges: Yes")
        print(f"✓ IMPORTANT: Change the password after first login!")
        
        return True

if __name__ == '__main__':
    print("=" * 60)
    print("BOWLS CLUB - Create Admin User")
    print("=" * 60)
    
    success = create_admin_user()
    
    if success:
        print("\nAdmin user created successfully!")
        print("You can now log in with:")
        print("  Username: admin")
        print("  Password: admin123")
        print("\nIMPORTANT: Change the password after your first login!")
    else:
        print("\nAdmin user creation skipped - users already exist.")
    
    print("\nDone!")