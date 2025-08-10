#!/usr/bin/env python3
"""
Single test validation to check basic functionality.
"""
import os
import sys

# Set environment variables
os.environ['FLASK_CONFIG'] = 'testing'
os.environ['SECRET_KEY'] = 'test-secret-key-for-testing-only'
os.environ['MAIL_SUPPRESS_SEND'] = 'true'

def test_imports():
    """Test that basic imports work."""
    print("Testing imports...")
    try:
        from app import create_app, db
        from app.models import Member, Role, Booking, Pool, PoolRegistration, Team, TeamMember
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_app_creation():
    """Test that app can be created."""
    print("Testing app creation...")
    try:
        from app import create_app
        app = create_app('testing')
        print("✓ App created successfully")
        return True
    except Exception as e:
        print(f"✗ App creation error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_booking_model():
    """Test that Booking model can be created with required fields."""
    print("Testing Booking model...")
    try:
        from app import create_app, db
        from app.models import Booking
        from datetime import date, timedelta
        
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            
            # Test creating a booking with all required fields
            booking = Booking(
                booking_date=date.today() + timedelta(days=1),
                session=1,
                rink_count=2,
                name='Test Booking',
                event_type=1,
                gender=4,
                format=5
            )
            db.session.add(booking)
            db.session.commit()
            
            # Test that it was created
            saved_booking = db.session.query(Booking).first()
            assert saved_booking is not None
            assert saved_booking.name == 'Test Booking'
            
            print("✓ Booking model works correctly")
            return True
    except Exception as e:
        print(f"✗ Booking model error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_conftest():
    """Test that conftest fixtures can be loaded."""
    print("Testing conftest...")
    try:
        from tests.conftest import app, client, db_session, test_member
        print("✓ Conftest fixtures load successfully")
        return True
    except Exception as e:
        print(f"✗ Conftest error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("=== Basic Test Validation ===")
    
    tests = [
        test_imports,
        test_app_creation,
        test_booking_model,
        test_conftest
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
            failed += 1
        print()
    
    print(f"=== Results: {passed} passed, {failed} failed ===")
    return failed == 0

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)