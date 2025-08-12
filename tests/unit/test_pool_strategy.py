"""
Unit tests for pool strategy functionality.
Tests the new pool strategy utilities and model methods that determine
pool creation behavior based on EVENT_POOL_STRATEGY configuration.
"""
import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from app.bookings.utils import (
    get_pool_strategy_for_booking,
    get_primary_booking_in_series, 
    should_create_pool_for_duplication,
    get_effective_pool_for_booking
)
from app.models import Booking, Pool, PoolRegistration, Member
from tests.fixtures.factories import BookingFactory, MemberFactory, PoolFactory


@pytest.mark.unit
class TestPoolStrategyUtils:
    """Test cases for pool strategy utility functions."""
    
    def test_get_pool_strategy_for_booking_social(self, app, db_session):
        """Test get_pool_strategy_for_booking returns 'booking' for Social events."""
        with app.app_context():
            booking = BookingFactory(event_type=1)  # Social
            db_session.commit()
            
            strategy = get_pool_strategy_for_booking(booking)
            assert strategy == 'booking'
    
    def test_get_pool_strategy_for_booking_competition(self, app, db_session):
        """Test get_pool_strategy_for_booking returns 'event' for Competition events."""
        with app.app_context():
            booking = BookingFactory(event_type=2)  # Competition  
            db_session.commit()
            
            strategy = get_pool_strategy_for_booking(booking)
            assert strategy == 'event'
    
    def test_get_pool_strategy_for_booking_league(self, app, db_session):
        """Test get_pool_strategy_for_booking returns 'event' for League events."""
        with app.app_context():
            booking = BookingFactory(event_type=3)  # League
            db_session.commit()
            
            strategy = get_pool_strategy_for_booking(booking)
            assert strategy == 'event'
    
    def test_get_pool_strategy_for_booking_friendly(self, app, db_session):
        """Test get_pool_strategy_for_booking returns 'booking' for Friendly events."""
        with app.app_context():
            booking = BookingFactory(event_type=4)  # Friendly
            db_session.commit()
            
            strategy = get_pool_strategy_for_booking(booking)
            assert strategy == 'booking'
    
    def test_get_pool_strategy_for_booking_rollup(self, app, db_session):
        """Test get_pool_strategy_for_booking returns 'none' for Roll Up events."""
        with app.app_context():
            booking = BookingFactory(event_type=5)  # Roll Up
            db_session.commit()
            
            strategy = get_pool_strategy_for_booking(booking)
            assert strategy == 'none'
    
    def test_get_pool_strategy_for_booking_other(self, app, db_session):
        """Test get_pool_strategy_for_booking returns 'event' for Other events."""
        with app.app_context():
            booking = BookingFactory(event_type=6)  # Other
            db_session.commit()
            
            strategy = get_pool_strategy_for_booking(booking)
            assert strategy == 'event'
    
    def test_get_pool_strategy_for_booking_unknown_type(self, app, db_session):
        """Test get_pool_strategy_for_booking defaults to 'booking' for unknown event types."""
        with app.app_context():
            booking = BookingFactory(event_type=99)  # Unknown type
            db_session.commit()
            
            strategy = get_pool_strategy_for_booking(booking)
            assert strategy == 'booking'
    
    def test_get_primary_booking_in_series_single_booking(self, app, db_session):
        """Test get_primary_booking_in_series returns the booking when series has one booking."""
        with app.app_context():
            booking = BookingFactory(series_id='test-series-1')
            db_session.commit()
            
            primary = get_primary_booking_in_series('test-series-1')
            assert primary is not None
            assert primary.id == booking.id
    
    def test_get_primary_booking_in_series_multiple_bookings(self, app, db_session):
        """Test get_primary_booking_in_series returns earliest booking by date."""
        with app.app_context():
            # Create bookings with different dates
            booking1 = BookingFactory(
                series_id='test-series-1',
                booking_date=date.today() + timedelta(days=5)
            )
            booking2 = BookingFactory(
                series_id='test-series-1', 
                booking_date=date.today() + timedelta(days=3)  # Earlier date
            )
            booking3 = BookingFactory(
                series_id='test-series-1',
                booking_date=date.today() + timedelta(days=7)
            )
            db_session.commit()
            
            primary = get_primary_booking_in_series('test-series-1')
            assert primary is not None
            assert primary.id == booking2.id  # Earliest by date
    
    def test_get_primary_booking_in_series_same_date_different_ids(self, app, db_session):
        """Test get_primary_booking_in_series uses ID as tiebreaker for same dates."""
        with app.app_context():
            same_date = date.today() + timedelta(days=5)
            
            # Create bookings with same date but different IDs
            booking1 = BookingFactory(series_id='test-series-1', booking_date=same_date)
            booking2 = BookingFactory(series_id='test-series-1', booking_date=same_date)
            db_session.commit()
            
            primary = get_primary_booking_in_series('test-series-1')
            assert primary is not None
            # Should return the one with lower ID (created first)
            assert primary.id == min(booking1.id, booking2.id)
    
    def test_get_primary_booking_in_series_nonexistent_series(self, app, db_session):
        """Test get_primary_booking_in_series returns None for nonexistent series."""
        with app.app_context():
            primary = get_primary_booking_in_series('nonexistent-series')
            assert primary is None
    
    def test_get_primary_booking_in_series_empty_series_id(self, app, db_session):
        """Test get_primary_booking_in_series returns None for empty series_id."""
        with app.app_context():
            primary = get_primary_booking_in_series('')
            assert primary is None
            
            primary = get_primary_booking_in_series(None)
            assert primary is None
    
    def test_should_create_pool_for_duplication_no_original_pool(self, app, db_session):
        """Test should_create_pool_for_duplication returns False when original has no pool."""
        with app.app_context():
            original = BookingFactory(has_pool=False)
            duplicate = BookingFactory()
            db_session.commit()
            
            should_create, reason = should_create_pool_for_duplication(original, duplicate)
            assert should_create is False
            assert "Original booking has no pool" in reason
    
    def test_should_create_pool_for_duplication_booking_strategy(self, app, db_session):
        """Test should_create_pool_for_duplication returns True for 'booking' strategy.""" 
        with app.app_context():
            # Create pool for original booking
            original = BookingFactory(event_type=1, has_pool=True)  # Social = 'booking' strategy
            pool = PoolFactory(booking_id=original.id)
            db_session.commit()
            original.pool = pool
            
            duplicate = BookingFactory()
            db_session.commit()
            
            should_create, reason = should_create_pool_for_duplication(original, duplicate)
            assert should_create is True
            assert "Strategy 'booking' - create new pool per booking" in reason
    
    def test_should_create_pool_for_duplication_event_strategy(self, app, db_session):
        """Test should_create_pool_for_duplication returns False for 'event' strategy."""
        with app.app_context():
            # Create pool for original booking
            original = BookingFactory(event_type=2, has_pool=True)  # Competition = 'event' strategy
            pool = PoolFactory(booking_id=original.id)  
            db_session.commit()
            original.pool = pool
            
            duplicate = BookingFactory()
            db_session.commit()
            
            should_create, reason = should_create_pool_for_duplication(original, duplicate)
            assert should_create is False
            assert "Strategy 'event' - will share pool with primary booking in series" in reason
    
    def test_should_create_pool_for_duplication_none_strategy(self, app, db_session):
        """Test should_create_pool_for_duplication returns False for 'none' strategy."""
        with app.app_context():
            # Create pool for original booking
            original = BookingFactory(event_type=5, has_pool=True)  # Roll Up = 'none' strategy
            pool = PoolFactory(booking_id=original.id)
            db_session.commit()
            original.pool = pool
            
            duplicate = BookingFactory()
            db_session.commit()
            
            should_create, reason = should_create_pool_for_duplication(original, duplicate)
            assert should_create is False
            assert "Strategy 'none' - no pool should be created" in reason
    
    @patch('app.bookings.utils.current_app')
    def test_should_create_pool_for_duplication_unknown_strategy(self, mock_app, app, db_session):
        """Test should_create_pool_for_duplication defaults to True for unknown strategy."""
        with app.app_context():
            # Mock logger and config with unknown strategy
            mock_logger = MagicMock()
            mock_config = MagicMock()
            mock_config.get.return_value = {99: 'unknown_strategy'}  # Configure unknown strategy for event_type 99
            mock_app.logger = mock_logger
            mock_app.config = mock_config
            
            # Create pool for original booking with unknown event type
            original = BookingFactory(event_type=99, has_pool=True)  # Unknown type
            pool = PoolFactory(booking_id=original.id)
            db_session.commit()  
            original.pool = pool
            
            duplicate = BookingFactory()
            db_session.commit()
            
            should_create, reason = should_create_pool_for_duplication(original, duplicate)
            assert should_create is True
            assert "Unknown strategy 'unknown_strategy' - defaulting to create new pool" in reason
            
            # Should log warning about unknown strategy
            mock_logger.warning.assert_called_once()
            warning_call = mock_logger.warning.call_args[0][0]
            assert "Unknown pool strategy 'unknown_strategy'" in warning_call
    
    def test_get_effective_pool_for_booking_own_pool(self, app, db_session):
        """Test get_effective_pool_for_booking returns booking's own pool."""
        with app.app_context():
            booking = BookingFactory()
            pool = PoolFactory(booking_id=booking.id)
            db_session.commit()
            booking.pool = pool
            
            effective_pool = get_effective_pool_for_booking(booking)
            assert effective_pool is not None
            assert effective_pool.id == pool.id
    
    def test_get_effective_pool_for_booking_no_series(self, app, db_session):
        """Test get_effective_pool_for_booking returns None when no series_id."""
        with app.app_context():
            booking = BookingFactory(series_id=None)
            db_session.commit()
            
            effective_pool = get_effective_pool_for_booking(booking)
            assert effective_pool is None
    
    def test_get_effective_pool_for_booking_non_event_strategy(self, app, db_session):
        """Test get_effective_pool_for_booking returns None for non-'event' strategies."""
        with app.app_context():
            # 'booking' strategy should not share pools
            booking = BookingFactory(event_type=1, series_id='test-series')  # Social = 'booking'
            db_session.commit()
            
            effective_pool = get_effective_pool_for_booking(booking)
            assert effective_pool is None
    
    def test_get_effective_pool_for_booking_event_strategy_shared_pool(self, app, db_session):
        """Test get_effective_pool_for_booking returns primary booking's pool for 'event' strategy."""
        with app.app_context():
            # Create primary booking with pool (earlier date)
            primary_booking = BookingFactory(
                event_type=2,  # Competition = 'event' strategy
                series_id='test-series', 
                booking_date=date.today() + timedelta(days=3)
            )
            pool = PoolFactory(booking_id=primary_booking.id)
            db_session.commit()
            primary_booking.pool = pool
            
            # Create secondary booking in same series (later date, no own pool)
            secondary_booking = BookingFactory(
                event_type=2,
                series_id='test-series',
                booking_date=date.today() + timedelta(days=5)
            )
            db_session.commit()
            
            # Secondary booking should get primary booking's pool
            effective_pool = get_effective_pool_for_booking(secondary_booking)
            assert effective_pool is not None
            assert effective_pool.id == pool.id
    
    def test_get_effective_pool_for_booking_primary_booking_is_self(self, app, db_session):
        """Test get_effective_pool_for_booking returns None when primary booking is self."""
        with app.app_context():
            # Single booking in series (is its own primary)
            booking = BookingFactory(
                event_type=2,  # Competition = 'event' strategy
                series_id='test-series'
            )
            db_session.commit()
            
            # Should return None because this booking is the primary, but has no pool
            effective_pool = get_effective_pool_for_booking(booking)
            assert effective_pool is None
    
    def test_get_effective_pool_for_booking_no_primary_in_series(self, app, db_session):
        """Test get_effective_pool_for_booking returns None when no primary found in series."""
        with app.app_context():
            # Create booking referencing non-existent series
            booking = BookingFactory(
                event_type=2,  # Competition = 'event' strategy
                series_id='nonexistent-series'
            )
            db_session.commit()
            
            effective_pool = get_effective_pool_for_booking(booking)
            assert effective_pool is None


@pytest.mark.unit
class TestBookingPoolStrategyMethods:
    """Test cases for Booking model pool strategy methods."""
    
    def test_booking_get_pool_strategy_social(self, app, db_session):
        """Test Booking.get_pool_strategy() returns 'booking' for Social events."""
        with app.app_context():
            booking = BookingFactory(event_type=1)  # Social
            db_session.commit()
            
            strategy = booking.get_pool_strategy()
            assert strategy == 'booking'
    
    def test_booking_get_pool_strategy_competition(self, app, db_session):
        """Test Booking.get_pool_strategy() returns 'event' for Competition events."""
        with app.app_context():
            booking = BookingFactory(event_type=2)  # Competition
            db_session.commit()
            
            strategy = booking.get_pool_strategy()
            assert strategy == 'event'
    
    def test_booking_get_pool_strategy_rollup(self, app, db_session):
        """Test Booking.get_pool_strategy() returns 'none' for Roll Up events."""
        with app.app_context():
            booking = BookingFactory(event_type=5)  # Roll Up
            db_session.commit()
            
            strategy = booking.get_pool_strategy()
            assert strategy == 'none'
    
    def test_booking_get_effective_pool_own_pool(self, app, db_session):
        """Test Booking.get_effective_pool() returns booking's own pool."""
        with app.app_context():
            booking = BookingFactory()
            pool = PoolFactory(booking_id=booking.id)
            db_session.commit()
            booking.pool = pool
            
            effective_pool = booking.get_effective_pool()
            assert effective_pool is not None
            assert effective_pool.id == pool.id
    
    def test_booking_get_effective_pool_shared_pool(self, app, db_session):
        """Test Booking.get_effective_pool() returns shared pool for event strategy."""
        with app.app_context():
            # Create primary booking with pool
            primary_booking = BookingFactory(
                event_type=2,  # Competition = 'event' strategy
                series_id='test-series',
                booking_date=date.today() + timedelta(days=3)
            )
            pool = PoolFactory(booking_id=primary_booking.id)
            db_session.commit()
            primary_booking.pool = pool
            
            # Create secondary booking in same series
            secondary_booking = BookingFactory(
                event_type=2,
                series_id='test-series', 
                booking_date=date.today() + timedelta(days=5)
            )
            db_session.commit()
            
            effective_pool = secondary_booking.get_effective_pool()
            assert effective_pool is not None
            assert effective_pool.id == pool.id
    
    def test_booking_has_effective_pool_true(self, app, db_session):
        """Test Booking.has_effective_pool() returns True when booking has effective pool."""
        with app.app_context():
            booking = BookingFactory()
            pool = PoolFactory(booking_id=booking.id)
            db_session.commit()
            booking.pool = pool
            
            assert booking.has_effective_pool() is True
    
    def test_booking_has_effective_pool_false(self, app, db_session):
        """Test Booking.has_effective_pool() returns False when booking has no effective pool."""
        with app.app_context():
            booking = BookingFactory(series_id=None)
            db_session.commit()
            
            assert booking.has_effective_pool() is False
    
    def test_booking_has_effective_pool_shared(self, app, db_session):
        """Test Booking.has_effective_pool() returns True for shared pool."""
        with app.app_context():
            # Create primary booking with pool
            primary_booking = BookingFactory(
                event_type=2,  # Competition = 'event' strategy
                series_id='test-series',
                booking_date=date.today() + timedelta(days=3)
            )
            pool = PoolFactory(booking_id=primary_booking.id)
            db_session.commit()
            primary_booking.pool = pool
            
            # Create secondary booking in same series
            secondary_booking = BookingFactory(
                event_type=2,
                series_id='test-series',
                booking_date=date.today() + timedelta(days=5)
            )
            db_session.commit()
            
            assert secondary_booking.has_effective_pool() is True
    
    def test_booking_get_effective_pool_member_count_own_pool(self, app, db_session):
        """Test Booking.get_effective_pool_member_count() counts members in own pool."""
        with app.app_context():
            booking = BookingFactory()
            pool = PoolFactory(booking_id=booking.id)
            
            # Create some members and registrations
            member1 = MemberFactory()
            member2 = MemberFactory()
            member3 = MemberFactory()
            
            reg1 = PoolRegistration(pool_id=pool.id, member_id=member1.id)
            reg2 = PoolRegistration(pool_id=pool.id, member_id=member2.id)
            reg3 = PoolRegistration(pool_id=pool.id, member_id=member3.id)
            
            db_session.add_all([reg1, reg2, reg3])
            db_session.commit()
            
            booking.pool = pool
            count = booking.get_effective_pool_member_count()
            assert count == 3
    
    def test_booking_get_effective_pool_member_count_shared_pool(self, app, db_session):
        """Test Booking.get_effective_pool_member_count() counts members in shared pool."""
        with app.app_context():
            # Create primary booking with pool
            primary_booking = BookingFactory(
                event_type=2,  # Competition = 'event' strategy
                series_id='test-series',
                booking_date=date.today() + timedelta(days=3)
            )
            pool = PoolFactory(booking_id=primary_booking.id)
            
            # Create some members and registrations
            member1 = MemberFactory()
            member2 = MemberFactory()
            
            reg1 = PoolRegistration(pool_id=pool.id, member_id=member1.id)
            reg2 = PoolRegistration(pool_id=pool.id, member_id=member2.id)
            
            db_session.add_all([reg1, reg2])
            db_session.commit()
            
            primary_booking.pool = pool
            
            # Create secondary booking in same series
            secondary_booking = BookingFactory(
                event_type=2,
                series_id='test-series',
                booking_date=date.today() + timedelta(days=5)
            )
            db_session.commit()
            
            count = secondary_booking.get_effective_pool_member_count()
            assert count == 2
    
    def test_booking_get_effective_pool_member_count_no_pool(self, app, db_session):
        """Test Booking.get_effective_pool_member_count() returns 0 when no pool."""
        with app.app_context():
            booking = BookingFactory(series_id=None)
            db_session.commit()
            
            count = booking.get_effective_pool_member_count()
            assert count == 0
    
    def test_booking_is_primary_booking_in_series_single_booking(self, app, db_session):
        """Test Booking.is_primary_booking_in_series() returns True for single booking."""
        with app.app_context():
            booking = BookingFactory(series_id=None)
            db_session.commit()
            
            assert booking.is_primary_booking_in_series() is True
    
    def test_booking_is_primary_booking_in_series_true(self, app, db_session):
        """Test Booking.is_primary_booking_in_series() returns True for primary booking."""
        with app.app_context():
            # Create multiple bookings, first one should be primary
            booking1 = BookingFactory(
                series_id='test-series',
                booking_date=date.today() + timedelta(days=3)  # Earlier
            )
            booking2 = BookingFactory(
                series_id='test-series',
                booking_date=date.today() + timedelta(days=5)  # Later
            )
            db_session.commit()
            
            assert booking1.is_primary_booking_in_series() is True
            assert booking2.is_primary_booking_in_series() is False
    
    def test_booking_is_primary_booking_in_series_false(self, app, db_session):
        """Test Booking.is_primary_booking_in_series() returns False for non-primary booking."""
        with app.app_context():
            # Create multiple bookings, second one should not be primary
            booking1 = BookingFactory(
                series_id='test-series',
                booking_date=date.today() + timedelta(days=3)  # Earlier
            )
            booking2 = BookingFactory(
                series_id='test-series',
                booking_date=date.today() + timedelta(days=5)  # Later
            )
            db_session.commit()
            
            assert booking2.is_primary_booking_in_series() is False
    
    def test_booking_is_primary_booking_in_series_id_tiebreaker(self, app, db_session):
        """Test Booking.is_primary_booking_in_series() uses ID as tiebreaker."""
        with app.app_context():
            same_date = date.today() + timedelta(days=5)
            
            # Create bookings with same date
            booking1 = BookingFactory(series_id='test-series', booking_date=same_date)
            booking2 = BookingFactory(series_id='test-series', booking_date=same_date)
            db_session.commit()
            
            # Only the one with lower ID should be primary
            lower_id_booking = booking1 if booking1.id < booking2.id else booking2
            higher_id_booking = booking2 if booking1.id < booking2.id else booking1
            
            assert lower_id_booking.is_primary_booking_in_series() is True
            assert higher_id_booking.is_primary_booking_in_series() is False


@pytest.mark.unit
class TestPoolStrategyEdgeCases:
    """Test edge cases for pool strategy functionality."""
    
    def test_should_create_pool_original_has_pool_false(self, app, db_session):
        """Test should_create_pool_for_duplication when original.has_pool is False."""
        with app.app_context():
            original = BookingFactory(has_pool=False)  # No pool flag
            pool = PoolFactory(booking_id=original.id)  # But has pool object
            db_session.commit()
            original.pool = pool
            
            duplicate = BookingFactory()
            db_session.commit()
            
            # Should return False because has_pool flag is False
            should_create, reason = should_create_pool_for_duplication(original, duplicate)
            assert should_create is False
            assert "Original booking has no pool" in reason
    
    def test_should_create_pool_original_pool_is_none(self, app, db_session):
        """Test should_create_pool_for_duplication when original.pool is None."""
        with app.app_context():
            original = BookingFactory(has_pool=True)  # Has pool flag
            db_session.commit()
            # But no actual pool object (original.pool is None)
            
            duplicate = BookingFactory()
            db_session.commit()
            
            # Should return False because pool object doesn't exist
            should_create, reason = should_create_pool_for_duplication(original, duplicate)
            assert should_create is False
            assert "Original booking has no pool" in reason
    
    def test_get_effective_pool_primary_has_no_pool(self, app, db_session):
        """Test get_effective_pool_for_booking when primary booking has no pool."""
        with app.app_context():
            # Create primary booking without pool
            primary_booking = BookingFactory(
                event_type=2,  # Competition = 'event' strategy
                series_id='test-series',
                booking_date=date.today() + timedelta(days=3)
            )
            
            # Create secondary booking in same series
            secondary_booking = BookingFactory(
                event_type=2,
                series_id='test-series',
                booking_date=date.today() + timedelta(days=5)
            )
            db_session.commit()
            
            # Secondary booking should get None (primary has no pool to share)
            effective_pool = get_effective_pool_for_booking(secondary_booking)
            assert effective_pool is None
    
    def test_booking_model_methods_with_corrupted_series(self, app, db_session):
        """Test Booking model methods handle corrupted series data gracefully."""
        with app.app_context():
            # Create booking with series_id but no other bookings in series exist
            orphaned_booking = BookingFactory(
                event_type=2,  # Competition = 'event' strategy  
                series_id='orphaned-series'
            )
            db_session.commit()
            
            # Should handle gracefully
            assert orphaned_booking.is_primary_booking_in_series() is True  # It's the only one
            assert orphaned_booking.get_effective_pool() is None  # No pool to share
            assert orphaned_booking.has_effective_pool() is False
            assert orphaned_booking.get_effective_pool_member_count() == 0
    
    def test_get_pool_strategy_with_config_modification(self, app, db_session):
        """Test pool strategy behavior when config is modified at runtime."""
        with app.app_context():
            booking = BookingFactory(event_type=1)  # Social
            db_session.commit()
            
            # Initially should be 'booking'
            assert booking.get_pool_strategy() == 'booking'
            
            # Simulate config change (in real app this would be in config file)
            original_config = app.config.get('EVENT_POOL_STRATEGY', {})
            modified_config = original_config.copy()
            modified_config[1] = 'event'  # Change Social to 'event' strategy
            
            with patch('app.bookings.utils.current_app') as mock_app:
                mock_config = MagicMock()
                mock_config.get.return_value = modified_config
                mock_app.config = mock_config
                
                # Should now return 'event'
                strategy = get_pool_strategy_for_booking(booking)
                assert strategy == 'event'
    
    def test_pool_registration_relationship_integrity(self, app, db_session):
        """Test that pool registration relationships work correctly with strategies."""
        with app.app_context():
            from app.models import PoolRegistration
            
            # Create booking with pool and registrations
            booking = BookingFactory(event_type=1)  # Social = 'booking' strategy
            pool = PoolFactory(booking_id=booking.id)
            
            # Create members and registrations
            members = [MemberFactory() for _ in range(3)]
            registrations = []
            for member in members:
                reg = PoolRegistration(pool_id=pool.id, member_id=member.id)
                registrations.append(reg)
                
            db_session.add_all(registrations)
            db_session.commit()
            
            booking.pool = pool
            
            # Test that relationships work correctly
            assert len(pool.registrations) == 3
            assert booking.get_effective_pool_member_count() == 3
            
            # Test each registration points to correct pool
            for reg in pool.registrations:
                assert reg.pool_id == pool.id
                assert reg.member_id in [m.id for m in members]
    
    def test_series_id_edge_cases(self, app, db_session):
        """Test edge cases with series_id values.""" 
        with app.app_context():
            # Test with empty string series_id
            booking_empty_series = BookingFactory(series_id='')
            db_session.commit()
            
            assert booking_empty_series.is_primary_booking_in_series() is True
            assert get_effective_pool_for_booking(booking_empty_series) is None
            
            # Test with whitespace-only series_id
            booking_whitespace_series = BookingFactory(series_id='   ')
            db_session.commit()
            
            primary = get_primary_booking_in_series('   ')
            assert primary is not None
            assert primary.id == booking_whitespace_series.id
    
    def test_pool_strategy_logging_verification(self, app, db_session):
        """Test that appropriate logging occurs for unknown strategies."""
        with app.app_context():
            # Create booking with unknown event type
            original = BookingFactory(event_type=999, has_pool=True)
            pool = PoolFactory(booking_id=original.id)
            db_session.commit()
            original.pool = pool
            
            duplicate = BookingFactory(event_type=999)
            db_session.commit()
            
            with patch('app.bookings.utils.current_app') as mock_app:
                mock_logger = MagicMock()
                mock_config = MagicMock()
                mock_config.get.return_value = {999: 'invalid_strategy'}  # Configure invalid strategy for event_type 999
                mock_app.logger = mock_logger
                mock_app.config = mock_config
                
                should_create, reason = should_create_pool_for_duplication(original, duplicate)
                
                # Should log warning for unknown strategy
                mock_logger.warning.assert_called_once()
                warning_call = mock_logger.warning.call_args[0][0]
                assert "Unknown pool strategy 'invalid_strategy'" in warning_call
                assert "defaulting to 'booking'" in warning_call