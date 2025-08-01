#!/usr/bin/env python3
"""Debug database configuration"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv
    load_dotenv('.flaskenv')
except ImportError:
    pass

from app import create_app

app = create_app()

with app.app_context():
    print("=== DATABASE CONFIGURATION DEBUG ===")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Script directory: {os.path.dirname(os.path.abspath(__file__))}")
    print(f"Database URL: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print(f"Database file path resolved: {app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')}")
    
    # Check if file exists and permissions  
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    if db_uri.startswith('sqlite:///'):
        db_path = db_uri[10:]  # Remove 'sqlite:///'
        if not db_path.startswith('/'):
            db_path = '/' + db_path  # Add leading slash if missing
    print(f"Database file exists: {os.path.exists(db_path)}")
    if os.path.exists(db_path):
        stat = os.stat(db_path)
        print(f"Database file permissions: {oct(stat.st_mode)[-3:]}")
        print(f"Database file owner: {stat.st_uid}")
        print(f"Database file group: {stat.st_gid}")
    
    print(f"Current process uid: {os.getuid()}")
    print(f"Current process gid: {os.getgid()}")
    
    # Check directory permissions
    db_dir = os.path.dirname(db_path)
    if os.path.exists(db_dir):
        dir_stat = os.stat(db_dir)
        print(f"Database directory permissions: {oct(dir_stat.st_mode)[-3:]}")
        print(f"Database directory owner: {dir_stat.st_uid}")
        
    # Test write access
    try:
        with open(db_path, 'r+b') as f:
            print("Database file is writable: Yes")
    except PermissionError:
        print("Database file is writable: No - Permission Error")
    except Exception as e:
        print(f"Database file write test failed: {e}")