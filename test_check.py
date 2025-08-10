#!/usr/bin/env python3
"""
Simple test check to validate imports and basic test structure.
"""
import os
import sys

# Set environment variables for testing
os.environ['FLASK_CONFIG'] = 'testing'
os.environ['SECRET_KEY'] = 'test-secret-key-for-testing-only'
os.environ['MAIL_SUPPRESS_SEND'] = 'true'

def check_imports():
    """Check if basic imports work."""
    try:
        # Basic Flask app import
        from app import create_app, db
        print("✓ App and db imports successful")
        
        # Model imports
        from app.models import Member, Role, Booking, Pool, Team
        print("✓ Model imports successful")
        
        # Test fixture imports
        from tests.fixtures.factories import MemberFactory, BookingFactory, RollUpBookingFactory, EventBookingFactory
        print("✓ Factory imports successful")
        
        # Try creating app
        app = create_app('testing')
        print("✓ App creation successful")
        
        # Try creating factories within app context
        with app.app_context():
            db.create_all()
            
            # Test basic factory creation
            member = MemberFactory.build()
            print(f"✓ MemberFactory build successful: {member.username}")
            
            booking = BookingFactory.build()
            print(f"✓ BookingFactory build successful: {booking.name}, type: {booking.booking_type}")
            
            rollup = RollUpBookingFactory.build()
            print(f"✓ RollUpBookingFactory build successful: {rollup.name}, type: {rollup.booking_type}")
            
            event_booking = EventBookingFactory.build()
            print(f"✓ EventBookingFactory build successful: {event_booking.name}, type: {event_booking.booking_type}")
            
            db.drop_all()
            
        return True
        
    except Exception as e:
        print(f"✗ Import check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_simple_test():
    """Run a simple test to check the test framework."""
    try:
        import pytest
        print("✓ pytest import successful")
        
        # Try importing a simple test
        from tests.unit.test_models import TestMemberModel
        print("✓ Test import successful")
        
        return True
        
    except Exception as e:
        print(f"✗ Test check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("=== Running Import Validation ===")
    imports_ok = check_imports()
    
    print("\n=== Running Test Framework Check ===")
    tests_ok = run_simple_test()
    
    print("\n=== Summary ===")
    if imports_ok and tests_ok:
        print("✓ All checks passed - ready to run tests")
        exit_code = 0
    else:
        print("✗ Some checks failed")
        exit_code = 1
        
    sys.exit(exit_code)