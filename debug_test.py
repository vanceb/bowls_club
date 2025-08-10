#!/usr/bin/env python3
"""
Debug test script to identify specific issues.
"""
import os
import sys

# Add the project root to the path
sys.path.insert(0, '/home/vance/code/bowls_club')

# Set environment variables
os.environ['FLASK_CONFIG'] = 'testing'
os.environ['SECRET_KEY'] = 'test-secret-key'

try:
    print("=== Testing app creation ===")
    from app import create_app
    app = create_app()
    print("App created successfully")
    
    print("\n=== Testing model imports ===")
    from app.models import Member, Role, Booking, Pool, Team
    print("Models imported successfully")
    
    print("\n=== Testing factory imports ===") 
    from tests.fixtures.factories import MemberFactory, BookingFactory
    print("Factories imported successfully")
    
    print("\n=== Testing conftest imports ===")
    from tests.conftest import app as test_app
    print("Conftest imported successfully")
    
    print("\n=== All imports successful ===")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()