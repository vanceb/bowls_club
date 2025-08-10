#!/usr/bin/env python3
"""
Simple validation script to check if basic test setup works.
"""
import os
import sys

def main():
    # Set environment variables
    os.environ['FLASK_CONFIG'] = 'testing'
    os.environ['SECRET_KEY'] = 'test-secret-key-for-testing-only'
    os.environ['MAIL_SUPPRESS_SEND'] = 'true'
    
    print("=== Validating Test Setup ===")
    
    try:
        print("1. Testing basic imports...")
        from app import create_app, db
        print("✓ Flask app imports successful")
        
        print("2. Testing model imports...")
        from app.models import Member, Role, Booking, Pool, PoolRegistration, Team, TeamMember
        print("✓ Model imports successful")
        
        print("3. Testing app creation...")
        app = create_app('testing')
        print("✓ App creation successful")
        
        print("4. Testing database creation...")
        with app.app_context():
            db.create_all()
            print("✓ Database creation successful")
        
        print("5. Testing conftest imports...")
        from tests.conftest import app as test_app_fixture
        print("✓ Conftest imports successful")
        
        print("\n=== All Validations Passed ===")
        return True
        
    except Exception as e:
        print(f"✗ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)