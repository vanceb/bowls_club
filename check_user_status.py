#!/usr/bin/env python3
"""Check user status and roles"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Member, Role

app = create_app()

with app.app_context():
    # Get all users
    users = db.session.query(Member).all()
    print(f"Total users in database: {len(users)}")
    print()
    
    for user in users:
        print(f"User: {user.username}")
        print(f"  - Name: {user.firstname} {user.lastname}")
        print(f"  - Email: {user.email}")
        print(f"  - Status: {user.status}")
        print(f"  - is_admin: {user.is_admin}")
        print(f"  - Roles: {[role.name for role in user.roles]}")
        print(f"  - has_role('Admin'): {user.has_role('Admin')}")
        print()
    
    # Get all roles
    roles = db.session.query(Role).all()
    print(f"Available roles: {[role.name for role in roles]}")