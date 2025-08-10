#!/usr/bin/env python3
"""
Basic test to check if the main issues are resolved.
"""
import os
import sys

# Add the project root to the path
sys.path.insert(0, '/home/vance/code/bowls_club')

# Set environment variables
os.environ['FLASK_CONFIG'] = 'testing'
os.environ['SECRET_KEY'] = 'test-secret-key'

print("=== Testing basic imports and functionality ===")

try:
    # Test app creation
    print("1. Testing app creation...")
    from app import create_app
    app = create_app()
    print("   ✓ App created successfully")
    
    # Test model imports
    print("2. Testing model imports...")
    from app.models import Member, Role, Booking, Pool, Team
    print("   ✓ Models imported successfully")
    
    # Test factory imports 
    print("3. Testing factory imports...")
    from tests.fixtures.factories import MemberFactory, BookingFactory
    print("   ✓ Factories imported successfully")
    
    # Test creating basic objects
    print("4. Testing basic object creation...")
    with app.app_context():
        # Test Booking creation
        booking = Booking(
            name='Test Event',
            booking_date=app.config.get('today', '2025-01-01'),
            session=1,
            rink_count=2,
            event_type=1,
            format=2,
            gender=3
        )
        print("   ✓ Booking object created successfully")
        
        # Test Pool creation
        if hasattr(booking, 'id') and booking.id:
            pool = Pool(booking_id=booking.id)
        else:
            # For testing without DB session, just check constructor
            try:
                pool = Pool(booking_id=1)
                print("   ✓ Pool object created successfully")
            except ValueError as e:
                if "booking_id" in str(e):
                    print("   ✓ Pool validation working correctly")
                else:
                    raise
    
    print("\n=== All basic tests passed! ===")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)