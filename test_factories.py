#!/usr/bin/env python3
"""
Test factories imports and basic usage.
"""
import os
import sys

# Set environment variables
os.environ['FLASK_CONFIG'] = 'testing'
os.environ['SECRET_KEY'] = 'test-secret-key-for-testing-only'
os.environ['MAIL_SUPPRESS_SEND'] = 'true'

def test_factory_imports():
    """Test that factory imports work."""
    print("Testing factory imports...")
    try:
        from tests.fixtures.factories import (
            MemberFactory, 
            RoleFactory, 
            BookingFactory, 
            EventBookingFactory,
            PoolFactory,
            TeamFactory
        )
        print("✓ All factory imports successful")
        return True
    except Exception as e:
        print(f"✗ Factory import error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_factory_imports()
    sys.exit(0 if success else 1)