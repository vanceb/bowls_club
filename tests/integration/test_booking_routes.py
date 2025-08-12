"""
Integration tests for main booking routes.
"""
import pytest
import json
from datetime import date, timedelta
from app.models import Member, Booking, Team, TeamMember
from tests.fixtures.factories import MemberFactory, BookingFactory


@pytest.mark.integration
class TestBookingRoutes:
    """Test cases for main booking routes."""
    
    def test_bookings_requires_login(self, client):
        """Test bookings page requires authentication."""
        response = client.get('/bookings/')
        assert response.status_code == 302  # Redirect to login
    
    def test_bookings_page_loads(self, authenticated_client):
        """Test bookings page loads for authenticated user."""
        response = authenticated_client.get('/bookings/')
        
        assert response.status_code == 200
        assert b'Bookings' in response.data
        assert b'Start Date' in response.data
        assert b'End Date' in response.data
        assert b'bookings-table-container' in response.data
    
    def test_get_bookings_requires_login(self, client):
        """Test get_bookings endpoint requires authentication."""
        test_date = date.today().isoformat()
        response = client.get(f'/bookings/get_bookings/{test_date}')
        assert response.status_code == 302  # Redirect to login
    
    def test_get_bookings_valid_date(self, authenticated_client, db_session):
        """Test get_bookings with valid date."""
        # Create test member and booking
        member = MemberFactory.create(
            username='testuser', firstname='Test', lastname='User',
            email='test@test.com', status='Full'
        )
        db_session.add(member)
        db_session.commit()
        
        test_date = date.today() + timedelta(days=1)
        booking = BookingFactory.create(
            name='Test Get Bookings',
            booking_date=test_date,
            session=1,
            rink_count=2,
            organizer=member,
            booking_type='event',
            organizer_notes='Test booking'
        )
        # Factory already commits
        
        response = authenticated_client.get(f'/bookings/get_bookings/{test_date.isoformat()}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['bookings']) == 1
        assert data['bookings'][0]['session'] == 1
        assert data['bookings'][0]['rink_count'] == 2
        assert data['bookings'][0]['organizer'] == 'Test User'
        assert data['total_rinks'] == 6
    
    def test_get_bookings_invalid_date(self, authenticated_client):
        """Test get_bookings with invalid date format."""
        response = authenticated_client.get('/bookings/get_bookings/invalid-date')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_get_bookings_range_requires_login(self, client):
        """Test get_bookings_range endpoint requires authentication."""
        start_date = date.today().isoformat()
        end_date = (date.today() + timedelta(days=7)).isoformat()
        response = client.get(f'/bookings/get_bookings_range/{start_date}/{end_date}')
        assert response.status_code == 302  # Redirect to login
    
    def test_get_bookings_range_valid_dates(self, authenticated_client, db_session):
        """Test get_bookings_range with valid date range."""
        # Create test member and bookings
        member = Member(
            username='testuser', firstname='Test', lastname='User',
            email='test@test.com', status='Full', joined_date=date.today()
        )
        db_session.add(member)
        db_session.commit()
        
        # Create bookings on different dates
        date1 = date.today() + timedelta(days=1)
        date2 = date.today() + timedelta(days=3)
        
        booking1 = Booking(
            name='Test Range Booking 1',
            booking_date=date1,
            session=1,
            rink_count=2,
            organizer=member,
            booking_type='event'
        )
        booking2 = Booking(
            name='Test Range Booking 2',
            booking_date=date2,
            session=2,
            rink_count=3,
            organizer=member,
            booking_type='rollup'
        )
        db_session.add_all([booking1, booking2])
        db_session.commit()
        
        start_date = date.today().isoformat()
        end_date = (date.today() + timedelta(days=7)).isoformat()
        
        response = authenticated_client.get(f'/bookings/get_bookings_range/{start_date}/{end_date}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['bookings']) == 2
        assert date1.isoformat() in data['bookings']
        assert date2.isoformat() in data['bookings']
        assert data['rinks'] == 6
        assert '1' in data['sessions']  # Session 1 exists in config
    
    def test_book_rollup_requires_login(self, client):
        """Test book rollup page requires authentication."""
        response = client.get('/rollups/book')
        assert response.status_code == 302  # Redirect to login
    
    def test_book_rollup_get_page_loads(self, authenticated_client):
        """Test book rollup GET page loads."""
        response = authenticated_client.get('/rollups/book')
        
        assert response.status_code == 200
        assert b'Book Roll-Up' in response.data
        assert b'booking_date' in response.data
        assert b'session' in response.data
        assert b'organizer_notes' in response.data
    
    def test_book_rollup_post_valid_data(self, authenticated_client, db_session, test_member):
        """Test book rollup POST with valid data."""
        # Update test_member in session
        db_session.add(test_member)
        db_session.commit()
        
        form_data = {
            'booking_date': (date.today() + timedelta(days=2)).isoformat(),
            'session': '2',
            'organizer_notes': 'Test rollup booking',
            'invited_players': '',
            'csrf_token': 'dummy'  # CSRF disabled in testing
        }
        
        response = authenticated_client.post('/rollups/book', 
                                           data=form_data, 
                                           follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Roll-up booking created successfully!' in response.data
        
        # Verify booking was created
        booking = db_session.query(Booking).filter_by(booking_type='rollup').first()
        assert booking is not None
        assert booking.organizer_id == test_member.id
        assert booking.rink_count == 1
        assert booking.organizer_notes == 'Test rollup booking'
        
        # Verify organizer was added as team member
        rollup_team = db_session.query(Team).filter_by(booking_id=booking.id).first()
        assert rollup_team is not None
        
        organizer_member = db_session.query(TeamMember).filter_by(
            team_id=rollup_team.id, 
            member_id=test_member.id
        ).first()
        assert organizer_member is not None
        assert organizer_member.availability_status == 'available'
    
    def test_respond_to_rollup_requires_login(self, client):
        """Test respond to rollup requires authentication."""
        response = client.get('/rollups/respond/1/accept')
        assert response.status_code == 302  # Redirect to login
    
    def test_respond_to_rollup_accept(self, authenticated_client, db_session, test_member):
        """Test accepting rollup invitation."""
        # Create organizer and booking
        organizer = MemberFactory.create(
            username='organizer', firstname='Organizer', lastname='User',
            email='organizer@test.com', status='Full'
        )
        db_session.add(organizer)
        db_session.commit()
        
        booking = BookingFactory.create(
            name='Test Rollup Booking',
            booking_date=date.today() + timedelta(days=2),
            session=2,
            rink_count=1,
            organizer=organizer,
            booking_type='rollup'
        )
        # Factory already commits
        
        # Create team for rollup
        rollup_team = Team(
            booking_id=booking.id,
            team_name=f"Roll-up {booking.booking_date}",
            created_by=organizer.id
        )
        db_session.add(rollup_team)
        db_session.commit()
        
        # Create invitation for test_member
        invitation = TeamMember(
            team_id=rollup_team.id,
            member_id=test_member.id,
            position='Player',
            availability_status='pending'
        )
        db_session.add(invitation)
        db_session.commit()
        
        response = authenticated_client.get(f'/rollups/respond/{booking.id}/accept',
                                          follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Roll-up invitation accepted!' in response.data
        
        # Verify invitation was updated
        db_session.refresh(invitation)
        assert invitation.availability_status == 'available'
        assert invitation.confirmed_at is not None
    
    def test_respond_to_rollup_decline(self, authenticated_client, db_session, test_member):
        """Test declining rollup invitation."""
        # Create organizer and booking
        organizer = MemberFactory.create(
            username='organizer', firstname='Organizer', lastname='User',
            email='organizer@test.com', status='Full'
        )
        db_session.add(organizer)
        db_session.commit()
        
        booking = BookingFactory.create(
            name='Test Rollup Booking',
            booking_date=date.today() + timedelta(days=2),
            session=2,
            rink_count=1,
            organizer=organizer,
            booking_type='rollup'
        )
        # Factory already commits
        
        # Create team for rollup
        rollup_team = Team(
            booking_id=booking.id,
            team_name=f"Roll-up {booking.booking_date}",
            created_by=organizer.id
        )
        db_session.add(rollup_team)
        db_session.commit()
        
        # Create invitation for test_member
        invitation = TeamMember(
            team_id=rollup_team.id,
            member_id=test_member.id,
            position='Player',
            availability_status='pending'
        )
        db_session.add(invitation)
        db_session.commit()
        
        response = authenticated_client.get(f'/rollups/respond/{booking.id}/decline',
                                          follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Roll-up invitation declined.' in response.data
        
        # Verify invitation was updated
        db_session.refresh(invitation)
        assert invitation.availability_status == 'unavailable'
        assert invitation.confirmed_at is not None
    
    def test_manage_rollup_requires_login(self, client):
        """Test manage rollup requires authentication."""
        response = client.get('/rollups/manage/1')
        assert response.status_code == 302  # Redirect to login
    
    def test_manage_rollup_organizer_only(self, authenticated_client, db_session, test_member):
        """Test manage rollup only accessible by organizer."""
        # Create different organizer
        organizer = MemberFactory.create(
            username='organizer', firstname='Organizer', lastname='User',
            email='organizer@test.com', status='Full'
        )
        db_session.add(organizer)
        db_session.commit()
        
        booking = BookingFactory.create(
            name='Test Rollup Booking',
            booking_date=date.today() + timedelta(days=2),
            session=2,
            rink_count=1,
            organizer=organizer,  # Different from test_member
            booking_type='rollup'
        )
        # Factory already commits
        
        response = authenticated_client.get(f'/rollups/manage/{booking.id}')
        assert response.status_code == 403  # Forbidden
    
    def test_manage_rollup_loads_for_organizer(self, authenticated_client, db_session, test_member):
        """Test manage rollup page loads for organizer."""
        booking = BookingFactory.create(
            name='Test Rollup Booking',
            booking_date=date.today() + timedelta(days=2),
            session=2,
            rink_count=1,
            organizer=test_member,
            booking_type='rollup',
            organizer_notes='Test rollup'
        )
        # Factory already commits
        
        response = authenticated_client.get(f'/rollups/manage/{booking.id}')
        
        assert response.status_code == 200
        assert b'Manage Roll-Up' in response.data
        assert b'Test rollup' in response.data
        assert b'Test User' in response.data  # Organizer name