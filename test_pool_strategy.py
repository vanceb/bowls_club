#!/usr/bin/env python3
"""
Test pool strategy functionality.
"""
import os
import sys

# Set environment variables
os.environ['FLASK_CONFIG'] = 'testing'
os.environ['SECRET_KEY'] = 'test-secret-key-for-testing-only'
os.environ['MAIL_SUPPRESS_SEND'] = 'true'

def test_pool_strategy_imports():
    """Test that pool strategy imports work."""
    print("Testing pool strategy imports...")
    try:
        from app.bookings.utils import (
            get_pool_strategy_for_booking,
            get_primary_booking_in_series,
            should_create_pool_for_duplication,
            get_effective_pool_for_booking
        )
        from app.models import Booking, Pool, PoolRegistration, Member
        from tests.fixtures.factories import BookingFactory, MemberFactory, PoolFactory
        print("✓ All pool strategy imports successful")
        return True
    except Exception as e:
        print(f"✗ Pool strategy import error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pool_strategy_basic_functionality():
    """Test basic pool strategy functionality."""
    print("\nTesting pool strategy basic functionality...")
    try:
        # Initialize Flask app
        from app import create_app, db
        app = create_app('testing')
        
        with app.app_context():
            # Create tables
            db.create_all()
            
            # Import required modules
            from app.bookings.utils import get_pool_strategy_for_booking
            from tests.fixtures.factories import BookingFactory
            
            # Test basic strategy retrieval
            social_booking = BookingFactory(event_type=1)  # Social
            db.session.commit()
            
            strategy = get_pool_strategy_for_booking(social_booking)
            assert strategy == 'booking', f"Expected 'booking', got '{strategy}'"
            
            competition_booking = BookingFactory(event_type=2)  # Competition
            db.session.commit()
            
            strategy = get_pool_strategy_for_booking(competition_booking)
            assert strategy == 'event', f"Expected 'event', got '{strategy}'"
            
            rollup_booking = BookingFactory(event_type=5)  # Roll Up
            db.session.commit()
            
            strategy = get_pool_strategy_for_booking(rollup_booking)
            assert strategy == 'none', f"Expected 'none', got '{strategy}'"
            
            print("✓ Basic pool strategy functionality working")
            
            # Clean up
            db.drop_all()
            
        return True
    except Exception as e:
        print(f"✗ Pool strategy functionality error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_booking_model_methods():
    """Test Booking model pool strategy methods."""
    print("\nTesting Booking model methods...")
    try:
        # Initialize Flask app
        from app import create_app, db
        app = create_app('testing')
        
        with app.app_context():
            # Create tables
            db.create_all()
            
            # Import required modules
            from tests.fixtures.factories import BookingFactory
            
            # Test model methods
            booking = BookingFactory(event_type=1)  # Social
            db.session.commit()
            
            # Test get_pool_strategy method
            strategy = booking.get_pool_strategy()
            assert strategy == 'booking', f"Expected 'booking', got '{strategy}'"
            
            # Test is_primary_booking_in_series method
            is_primary = booking.is_primary_booking_in_series()
            assert is_primary is True, f"Expected True, got {is_primary}"
            
            # Test has_effective_pool method (should be False initially)
            has_pool = booking.has_effective_pool()
            assert has_pool is False, f"Expected False, got {has_pool}"
            
            # Test member count (should be 0 initially)
            count = booking.get_effective_pool_member_count()
            assert count == 0, f"Expected 0, got {count}"
            
            print("✓ Booking model methods working")
            
            # Clean up
            db.drop_all()
            
        return True
    except Exception as e:
        print(f"✗ Booking model methods error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("=== Pool Strategy Testing ===")
    
    success = True
    
    # Test imports
    if not test_pool_strategy_imports():
        success = False
    
    # Test basic functionality
    if success and not test_pool_strategy_basic_functionality():
        success = False
    
    # Test model methods
    if success and not test_booking_model_methods():
        success = False
    
    if success:
        print("\n✅ All pool strategy tests passed!")
    else:
        print("\n❌ Some pool strategy tests failed!")
    
    sys.exit(0 if success else 1)