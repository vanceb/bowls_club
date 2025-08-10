#!/usr/bin/env python3
"""
Diagnostic test to identify remaining issues with the test suite.
"""
import os
import sys

# Set environment variables
os.environ['FLASK_CONFIG'] = 'testing'
os.environ['SECRET_KEY'] = 'test-secret-key-for-testing-only'
os.environ['MAIL_SUPPRESS_SEND'] = 'true'

def test_basic_setup():
    """Test basic Flask setup."""
    try:
        from app import create_app, db
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            print("✓ Basic Flask setup works")
            return True
    except Exception as e:
        print(f"✗ Basic Flask setup failed: {e}")
        return False

def test_models():
    """Test model creation."""
    try:
        from app import create_app, db
        from app.models import Member, Booking, Team, Pool
        from datetime import date, timedelta
        
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            
            # Test Member creation
            member = Member(
                username='testuser',
                firstname='Test',
                lastname='User',
                email='test@example.com',
                status='Full'
            )
            db.session.add(member)
            db.session.commit()
            
            # Test Booking creation with new required fields
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
            
            # Test Team creation with new status field
            team = Team(
                team_name='Test Team',
                created_by=member.id,
                booking_id=booking.id
                # status defaults to 'draft'
            )
            db.session.add(team)
            db.session.commit()
            
            # Test Pool creation
            pool = Pool(booking_id=booking.id)
            db.session.add(pool)
            db.session.commit()
            
            # Test Team finalization (new functionality)
            assert team.status == 'draft'
            assert team.can_be_modified() is True
            assert team.is_finalized() is False
            
            result = team.finalize_team()
            assert result is True
            assert team.status == 'finalized'
            assert team.is_finalized() is True
            assert team.can_be_modified() is False
            
            db.session.commit()
            
            print("✓ All models work correctly with new fields")
            return True
    except Exception as e:
        print(f"✗ Model test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_conftest_fixtures():
    """Test conftest fixtures."""
    try:
        from tests.conftest import app, test_booking, test_pool
        print("✓ Conftest fixtures load correctly")
        return True
    except Exception as e:
        print(f"✗ Conftest fixtures failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=== Diagnostic Test Report ===")
    
    tests = [
        ("Basic Setup", test_basic_setup),
        ("Model Operations", test_models),
        ("Conftest Fixtures", test_conftest_fixtures)
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        print(f"\nTesting {name}...")
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ {name} failed with exception: {e}")
            failed += 1
    
    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    
    if failed == 0:
        print("✓ All diagnostic tests passed - test suite should work correctly")
    else:
        print("✗ Some issues remain that need to be addressed")
    
    return failed == 0

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)