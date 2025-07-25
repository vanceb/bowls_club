"""
Unit tests for booking utility functions.
"""
import pytest
import sqlalchemy as sa
from app.bookings.utils import add_home_games_filter
from app.models import Booking, Member


@pytest.mark.unit
class TestBookingUtils:
    """Test cases for booking utility functions."""
    
    def test_add_home_games_filter_basic_query(self, app, db_session):
        """Test add_home_games_filter with basic query."""
        with app.app_context():
            # Create test member
            member = Member(
                username='testuser', firstname='Test', lastname='User',
                email='test@test.com', status='Full'
            )
            db_session.add(member)
            db_session.commit()
            
            # Create test bookings
            home_booking = Booking(
                booking_date=sa.func.date('2024-01-01'),
                session=1,
                rink_count=2,
                organizer_id=member.id,
                home_away='home'
            )
            away_booking = Booking(
                booking_date=sa.func.date('2024-01-02'),
                session=1,
                rink_count=3,
                organizer_id=member.id,
                home_away='away'
            )
            neutral_booking = Booking(
                booking_date=sa.func.date('2024-01-03'),
                session=1,
                rink_count=1,
                organizer_id=member.id,
                home_away='neutral'
            )
            null_booking = Booking(
                booking_date=sa.func.date('2024-01-04'),
                session=1,
                rink_count=4,
                organizer_id=member.id,
                home_away=None
            )
            
            db_session.add_all([home_booking, away_booking, neutral_booking, null_booking])
            db_session.commit()
            
            # Test basic query
            base_query = sa.select(Booking)
            filtered_query = add_home_games_filter(base_query)
            
            results = db_session.scalars(filtered_query).all()
            
            # Should return home, neutral, and null bookings but not away
            assert len(results) == 3
            home_away_values = [booking.home_away for booking in results]
            assert 'home' in home_away_values
            assert 'neutral' in home_away_values
            assert None in home_away_values
            assert 'away' not in home_away_values
    
    def test_add_home_games_filter_sum_query(self, app, db_session):
        """Test add_home_games_filter with sum aggregation query."""
        with app.app_context():
            # Create test member
            member = Member(
                username='testuser', firstname='Test', lastname='User',
                email='test@test.com', status='Full'
            )
            db_session.add(member)
            db_session.commit()
            
            # Create test bookings
            home_booking = Booking(
                booking_date=sa.func.date('2024-01-01'),
                session=1,
                rink_count=2,
                organizer_id=member.id,
                home_away='home'
            )
            away_booking = Booking(
                booking_date=sa.func.date('2024-01-01'),
                session=1,
                rink_count=3,
                organizer_id=member.id,
                home_away='away'
            )
            neutral_booking = Booking(
                booking_date=sa.func.date('2024-01-01'),
                session=1,
                rink_count=1,
                organizer_id=member.id,
                home_away='neutral'
            )
            
            db_session.add_all([home_booking, away_booking, neutral_booking])
            db_session.commit()
            
            # Test sum query (commonly used for availability calculations)
            base_query = sa.select(sa.func.sum(Booking.rink_count)).where(
                Booking.booking_date == sa.func.date('2024-01-01'),
                Booking.session == 1
            )
            filtered_query = add_home_games_filter(base_query)
            
            result = db_session.scalar(filtered_query)
            
            # Should sum home (2) + neutral (1) = 3, excluding away (3)
            assert result == 3
    
    def test_add_home_games_filter_empty_result(self, app, db_session):
        """Test add_home_games_filter with no matching results."""
        with app.app_context():
            # Test with empty database
            base_query = sa.select(Booking)
            filtered_query = add_home_games_filter(base_query)
            
            results = db_session.scalars(filtered_query).all()
            assert len(results) == 0
    
    def test_add_home_games_filter_only_away_games(self, app, db_session):
        """Test add_home_games_filter when only away games exist."""
        with app.app_context():
            # Create test member
            member = Member(
                username='testuser', firstname='Test', lastname='User',
                email='test@test.com', status='Full'
            )
            db_session.add(member)
            db_session.commit()
            
            # Create only away bookings
            away_booking1 = Booking(
                booking_date=sa.func.date('2024-01-01'),
                session=1,
                rink_count=2,
                organizer_id=member.id,
                home_away='away'
            )
            away_booking2 = Booking(
                booking_date=sa.func.date('2024-01-01'),
                session=2,
                rink_count=3,
                organizer_id=member.id,
                home_away='away'
            )
            
            db_session.add_all([away_booking1, away_booking2])
            db_session.commit()
            
            # Test query should return no results
            base_query = sa.select(Booking)
            filtered_query = add_home_games_filter(base_query)
            
            results = db_session.scalars(filtered_query).all()
            assert len(results) == 0
            
            # Test sum query should return None/0
            sum_query = sa.select(sa.func.sum(Booking.rink_count))
            filtered_sum_query = add_home_games_filter(sum_query)
            
            sum_result = db_session.scalar(filtered_sum_query)
            assert sum_result is None or sum_result == 0
    
    def test_add_home_games_filter_with_additional_conditions(self, app, db_session):
        """Test add_home_games_filter combined with other query conditions."""
        with app.app_context():
            # Create test member
            member = Member(
                username='testuser', firstname='Test', lastname='User',
                email='test@test.com', status='Full'
            )
            db_session.add(member)
            db_session.commit()
            
            # Create test bookings on different dates
            home_booking_jan = Booking(
                booking_date=sa.func.date('2024-01-01'),
                session=1,
                rink_count=2,
                organizer_id=member.id,
                home_away='home'
            )
            home_booking_feb = Booking(
                booking_date=sa.func.date('2024-02-01'),
                session=1,
                rink_count=3,
                organizer_id=member.id,
                home_away='home'
            )
            away_booking_jan = Booking(
                booking_date=sa.func.date('2024-01-01'),
                session=1,
                rink_count=1,
                organizer_id=member.id,
                home_away='away'
            )
            
            db_session.add_all([home_booking_jan, home_booking_feb, away_booking_jan])
            db_session.commit()
            
            # Test with additional date filter
            base_query = sa.select(Booking).where(
                Booking.booking_date == sa.func.date('2024-01-01')
            )
            filtered_query = add_home_games_filter(base_query)
            
            results = db_session.scalars(filtered_query).all()
            
            # Should only return the January home booking
            assert len(results) == 1
            assert results[0].home_away == 'home'
            assert results[0].rink_count == 2