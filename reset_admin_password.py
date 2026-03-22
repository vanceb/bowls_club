#!/usr/bin/env python3
"""
Reset Administrator Password Script
This script resets the password for the administrator account.
"""

import os
import sys

# Load environment variables from .flaskenv
from dotenv import load_dotenv
load_dotenv('.flaskenv')

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import Member
import sqlalchemy as sa

def reset_admin_password():
    """Reset the administrator account password."""

    # Create Flask app context
    app = create_app()

    with app.app_context():
        # Find the administrator account (is_admin=True)
        admin = db.session.scalar(
            sa.select(Member).where(Member.is_admin == True)
        )

        if not admin:
            print("ERROR: No administrator account found in the database.")
            print("Please create an administrator account first.")
            return False

        # Set a simple password
        new_password = "admin123"
        admin.set_password(new_password)

        # Commit the change
        try:
            db.session.commit()
            print(f"✓ Password reset successful!")
            print(f"  Username: {admin.username}")
            print(f"  Email: {admin.email}")
            print(f"  New password: {new_password}")
            print(f"\nIMPORTANT: Please change this password after logging in!")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"ERROR: Failed to update password: {str(e)}")
            return False

if __name__ == "__main__":
    success = reset_admin_password()
    sys.exit(0 if success else 1)
