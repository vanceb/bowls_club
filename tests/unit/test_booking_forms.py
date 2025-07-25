"""
Unit tests for booking forms validation.
"""
import pytest
from datetime import date, timedelta
from app.bookings.forms import BookingForm, RollUpBookingForm
from app.models import Member, Booking


@pytest.mark.unit
class TestBookingForm:
    """Test cases for BookingForm."""
    
    def test_valid_booking_form(self, app):
        """Test valid booking form data."""
        with app.app_context():
            form_data = {
                'booking_date': date.today() + timedelta(days=1),
                'session': 1,
                'rink_count': 2,
                'priority': 'High',
                'vs': 'Test Opposition',
                'home_away': 'home'
            }
            form = BookingForm(data=form_data)
            
            assert form.validate() is True
            assert form.booking_date.data == form_data['booking_date']
            assert form.session.data == 1
            assert form.rink_count.data == 2
            assert form.priority.data == 'High'
            assert form.vs.data == 'Test Opposition'
            assert form.home_away.data == 'home'
    
    def test_booking_form_required_fields(self, app):
        """Test booking form with missing required fields."""
        with app.app_context():
            form = BookingForm(data={})
            
            assert form.validate() is False
            assert 'This field is required.' in form.booking_date.errors
            assert 'This field is required.' in form.session.errors
            assert 'This field is required.' in form.rink_count.errors
    
    def test_booking_form_rink_count_validation(self, app):
        """Test rink count validation."""
        with app.app_context():
            # Test with 0 rinks (invalid)
            form_data = {
                'booking_date': date.today() + timedelta(days=1),
                'session': 1,
                'rink_count': 0
            }
            form = BookingForm(data=form_data)
            
            assert form.validate() is False
            assert any('Number must be between 1 and' in error for error in form.rink_count.errors)
    
    def test_booking_form_rink_count_exceeds_maximum(self, app):
        """Test rink count exceeding maximum."""
        with app.app_context():
            # Test with more than maximum rinks (should be 6 from config)
            form_data = {
                'booking_date': date.today() + timedelta(days=1),
                'session': 1,
                'rink_count': 10
            }
            form = BookingForm(data=form_data)
            
            assert form.validate() is False
            assert any('Number must be between 1 and' in error for error in form.rink_count.errors)
    
    def test_booking_form_rink_availability_validation(self, app, db_session):
        """Test rink availability validation."""
        with app.app_context():
            # Create an existing booking that uses 5 rinks
            test_date = date.today() + timedelta(days=1)
            existing_member = Member(
                username='existing', firstname='Existing', lastname='User',
                email='existing@test.com', status='Full'
            )
            db_session.add(existing_member)
            db_session.commit()
            
            existing_booking = Booking(
                booking_date=test_date,
                session=1,
                rink_count=5,
                organizer_id=existing_member.id,
                home_away='home'
            )
            db_session.add(existing_booking)
            db_session.commit()
            
            # Try to book 3 more rinks (should fail as only 1 available)
            form_data = {
                'booking_date': test_date,
                'session': 1,
                'rink_count': 3
            }
            form = BookingForm(data=form_data)
            
            assert form.validate() is False
            assert any('Only 1 rink(s) available' in error for error in form.rink_count.errors)
    
    def test_booking_form_away_games_not_counted_in_availability(self, app, db_session):
        """Test that away games don't count against rink availability."""
        with app.app_context():
            # Create an away game booking
            test_date = date.today() + timedelta(days=1)
            existing_member = Member(
                username='existing', firstname='Existing', lastname='User',
                email='existing@test.com', status='Full'
            )
            db_session.add(existing_member)
            db_session.commit()
            
            away_booking = Booking(
                booking_date=test_date,
                session=1,
                rink_count=6,  # All rinks, but away
                organizer_id=existing_member.id,
                home_away='away'
            )
            db_session.add(away_booking)
            db_session.commit()
            
            # Should still be able to book home games
            form_data = {
                'booking_date': test_date,
                'session': 1,
                'rink_count': 6
            }
            form = BookingForm(data=form_data)
            
            assert form.validate() is True


@pytest.mark.unit
class TestRollUpBookingForm:
    """Test cases for RollUpBookingForm."""
    
    def test_valid_rollup_form(self, app):
        """Test valid roll-up booking form data."""
        with app.app_context():
            form_data = {
                'booking_date': date.today() + timedelta(days=2),
                'session': 2,
                'organizer_notes': 'Test roll-up notes',
                'invited_players': '1,2,3'
            }
            form = RollUpBookingForm(data=form_data)
            
            assert form.validate() is True
            assert form.booking_date.data == form_data['booking_date']
            assert form.session.data == 2
            assert form.organizer_notes.data == 'Test roll-up notes'
            assert form.invited_players.data == '1,2,3'
    
    def test_rollup_form_required_fields(self, app):
        """Test roll-up form with missing required fields."""
        with app.app_context():
            form = RollUpBookingForm(data={})
            
            assert form.validate() is False
            assert 'This field is required.' in form.booking_date.errors
            assert 'This field is required.' in form.session.errors
    
    def test_rollup_form_optional_fields(self, app):
        """Test roll-up form with only required fields."""
        with app.app_context():
            form_data = {
                'booking_date': date.today() + timedelta(days=2),
                'session': 2
            }
            form = RollUpBookingForm(data=form_data)
            
            assert form.validate() is True
            assert form.organizer_notes.data is None or form.organizer_notes.data == ''
            assert form.invited_players.data is None or form.invited_players.data == ''
    
    def test_rollup_form_past_date_validation(self, app):
        """Test roll-up booking for past date is invalid."""
        with app.app_context():
            form_data = {
                'booking_date': date.today() - timedelta(days=1),
                'session': 2
            }
            form = RollUpBookingForm(data=form_data)
            
            assert form.validate() is False
            assert 'Roll-up bookings cannot be made for past dates' in form.booking_date.errors
    
    def test_rollup_form_advance_booking_limit(self, app):
        """Test roll-up advance booking limit validation."""
        with app.app_context():
            # Try to book 10 days in advance (should fail with 7-day limit)
            form_data = {
                'booking_date': date.today() + timedelta(days=10),
                'session': 2
            }
            form = RollUpBookingForm(data=form_data)
            
            assert form.validate() is False
            assert 'Roll-up bookings can only be made 7 days in advance' in form.booking_date.errors
    
    def test_rollup_form_max_players_validation(self, app):
        """Test maximum players validation."""
        with app.app_context():
            # Invite 9 players (should fail with max 8 total)
            form_data = {
                'booking_date': date.today() + timedelta(days=2),
                'session': 2,
                'invited_players': '1,2,3,4,5,6,7,8,9'
            }
            form = RollUpBookingForm(data=form_data)
            
            assert form.validate() is False
            assert 'Maximum 8 players allowed per roll-up' in form.invited_players.errors
    
    def test_rollup_form_rink_availability_validation(self, app, db_session):
        """Test roll-up rink availability validation."""
        with app.app_context():
            # Note: RollUpBookingForm doesn't have session-level availability validation
            # It relies on the booking creation logic to check availability
            # This test verifies the form validates successfully even with existing bookings
            test_date = date.today() + timedelta(days=2)
            existing_member = Member(
                username='existing', firstname='Existing', lastname='User',
                email='existing@test.com', status='Full'
            )
            db_session.add(existing_member)
            db_session.commit()
            
            existing_booking = Booking(
                booking_date=test_date,
                session=2,
                rink_count=6,
                organizer_id=existing_member.id,
                home_away='home'
            )
            db_session.add(existing_booking)
            db_session.commit()
            
            # Try to book roll-up (form should validate, availability checked at booking time)
            form_data = {
                'booking_date': test_date,
                'session': 2
            }
            form = RollUpBookingForm(data=form_data)
            
            # Form validation should pass, availability is checked during booking creation
            assert form.validate() is True
    
    def test_rollup_form_notes_length_validation(self, app):
        """Test organizer notes length validation."""
        with app.app_context():
            long_notes = 'a' * 600  # Exceeds 500 character limit
            form_data = {
                'booking_date': date.today() + timedelta(days=2),
                'session': 2,
                'organizer_notes': long_notes
            }
            form = RollUpBookingForm(data=form_data)
            
            assert form.validate() is False
            assert any('Field cannot be longer than 500 characters' in error 
                      for error in form.organizer_notes.errors)
    
    def test_rollup_form_invalid_player_ids(self, app):
        """Test roll-up form with invalid player IDs."""
        with app.app_context():
            form_data = {
                'booking_date': date.today() + timedelta(days=2),
                'session': 2,
                'invited_players': 'invalid,player,ids'
            }
            form = RollUpBookingForm(data=form_data)
            
            # Should fail validation due to invalid player ID format
            assert form.validate() is False
            assert 'Invalid player selection format' in form.invited_players.errors