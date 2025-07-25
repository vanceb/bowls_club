"""
Integration tests for booking API routes.
"""
import pytest
import json
from datetime import date, timedelta
from app.models import Member, Booking, Event


@pytest.mark.integration
class TestBookingAPIRoutes:
    """Test cases for booking API routes."""
    
    def test_api_booking_get_requires_login(self, client):
        """Test API booking GET requires authentication."""
        response = client.get('/bookings/api/v1/booking/1')
        assert response.status_code == 302  # Redirect to login
    
    def test_api_booking_get_not_found(self, authenticated_client):
        """Test API booking GET with non-existent booking."""
        response = authenticated_client.get('/bookings/api/v1/booking/999')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'not found' in data['error'].lower()
    
    def test_api_booking_get_success(self, authenticated_client, db_session):
        """Test API booking GET with existing booking."""
        # Create test member and booking
        member = Member(
            username='testuser', firstname='Test', lastname='User',
            email='test@test.com', status='Full'
        )
        db_session.add(member)
        db_session.commit()
        
        booking = Booking(
            booking_date=date.today() + timedelta(days=1),
            session=1,
            rink_count=2,
            organizer_id=member.id,
            booking_type='event',
            priority='High',
            vs='Test Opposition',
            home_away='home',
            organizer_notes='Test notes'
        )
        db_session.add(booking)
        db_session.commit()
        
        response = authenticated_client.get(f'/bookings/api/v1/booking/{booking.id}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        
        booking_data = data['booking']
        assert booking_data['id'] == booking.id
        assert booking_data['booking_date'] == booking.booking_date.isoformat()
        assert booking_data['session'] == 1
        assert booking_data['rink_count'] == 2
        assert booking_data['booking_type'] == 'event'
        assert booking_data['priority'] == 'High'
        assert booking_data['vs'] == 'Test Opposition'
        assert booking_data['home_away'] == 'home'
        assert booking_data['organizer_notes'] == 'Test notes'
        assert booking_data['organizer_name'] == 'Test User'
    
    def test_api_booking_get_with_event(self, authenticated_client, db_session):
        """Test API booking GET with associated event."""
        # Create test member and event
        member = Member(
            username='testuser', firstname='Test', lastname='User',
            email='test@test.com', status='Full'
        )
        db_session.add(member)
        db_session.commit()
        
        event = Event(
            name='Test Championship',
            event_date=date.today() + timedelta(days=1),
            event_type=2,  # Competition
            format=3,  # Triples
            gender=1,  # Gents
            organizer_id=member.id
        )
        db_session.add(event)
        db_session.commit()
        
        booking = Booking(
            booking_date=date.today() + timedelta(days=1),
            session=1,
            rink_count=3,
            organizer_id=member.id,
            event_id=event.id,
            vs='Championship Opponents'
        )
        db_session.add(booking)
        db_session.commit()
        
        response = authenticated_client.get(f'/bookings/api/v1/booking/{booking.id}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        
        booking_data = data['booking']
        assert booking_data['event_id'] == event.id
        assert booking_data['event_name'] == 'Test Championship'
        assert booking_data['vs'] == 'Championship Opponents'
    
    def test_api_booking_put_requires_login(self, client):
        """Test API booking PUT requires authentication."""
        response = client.put('/bookings/api/v1/booking/1')
        assert response.status_code == 302  # Redirect to login
    
    def test_api_booking_put_requires_event_manager(self, authenticated_client):
        """Test API booking PUT requires Event Manager role."""
        response = authenticated_client.put('/bookings/api/v1/booking/1')
        assert response.status_code == 302  # Redirect due to role requirement
    
    def test_api_booking_put_not_found(self, admin_client):
        """Test API booking PUT with non-existent booking."""
        response = admin_client.put('/bookings/api/v1/booking/999',
                                  json={'rink_count': 3})
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'not found' in data['error'].lower()
    
    def test_api_booking_put_success(self, admin_client, db_session):
        """Test API booking PUT with valid data."""
        # Create test member and booking
        member = Member(
            username='testuser', firstname='Test', lastname='User',
            email='test@test.com', status='Full'
        )
        db_session.add(member)
        db_session.commit()
        
        booking = Booking(
            booking_date=date.today() + timedelta(days=1),
            session=1,
            rink_count=2,
            organizer_id=member.id,
            priority='High',
            vs='Original Opposition'
        )
        db_session.add(booking)
        db_session.commit()
        
        update_data = {
            'rink_count': 3,
            'priority': 'Medium',
            'vs': 'Updated Opposition',
            'organizer_notes': 'Updated notes'
        }
        
        response = admin_client.put(f'/bookings/api/v1/booking/{booking.id}',
                                  json=update_data)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['message'] == 'Booking updated successfully'
        
        # Verify booking was updated
        db_session.refresh(booking)
        assert booking.rink_count == 3
        assert booking.priority == 'Medium'
        assert booking.vs == 'Updated Opposition'
        assert booking.organizer_notes == 'Updated notes'
    
    def test_api_booking_put_invalid_data(self, admin_client, db_session):
        """Test API booking PUT with invalid data."""
        # Create test member and booking
        member = Member(
            username='testuser', firstname='Test', lastname='User',
            email='test@test.com', status='Full'
        )
        db_session.add(member)
        db_session.commit()
        
        booking = Booking(
            booking_date=date.today() + timedelta(days=1),
            session=1,
            rink_count=2,
            organizer_id=member.id
        )
        db_session.add(booking)
        db_session.commit()
        
        # Try to set invalid rink count
        update_data = {
            'rink_count': 0  # Invalid - should be >= 1
        }
        
        response = admin_client.put(f'/bookings/api/v1/booking/{booking.id}',
                                  json=update_data)
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'invalid' in data['error'].lower()
    
    def test_api_booking_delete_requires_login(self, client):
        """Test API booking DELETE requires authentication."""
        response = client.delete('/bookings/api/v1/booking/1')
        assert response.status_code == 302  # Redirect to login
    
    def test_api_booking_delete_requires_event_manager(self, authenticated_client):
        """Test API booking DELETE requires Event Manager role."""
        response = authenticated_client.delete('/bookings/api/v1/booking/1')
        assert response.status_code == 302  # Redirect due to role requirement
    
    def test_api_booking_delete_not_found(self, admin_client):
        """Test API booking DELETE with non-existent booking."""
        response = admin_client.delete('/bookings/api/v1/booking/999')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'not found' in data['error'].lower()
    
    def test_api_booking_delete_success(self, admin_client, db_session):
        """Test API booking DELETE with existing booking."""
        # Create test member and booking
        member = Member(
            username='testuser', firstname='Test', lastname='User',
            email='test@test.com', status='Full'
        )
        db_session.add(member)
        db_session.commit()
        
        booking = Booking(
            booking_date=date.today() + timedelta(days=1),
            session=1,
            rink_count=2,
            organizer_id=member.id
        )
        db_session.add(booking)
        db_session.commit()
        
        booking_id = booking.id
        
        response = admin_client.delete(f'/bookings/api/v1/booking/{booking_id}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['message'] == 'Booking deleted successfully'
        
        # Verify booking was deleted
        deleted_booking = db_session.get(Booking, booking_id)
        assert deleted_booking is None
    
    def test_api_booking_delete_with_teams(self, admin_client, db_session):
        """Test API booking DELETE cascades to teams and team members."""
        from app.models import BookingTeam, BookingTeamMember
        
        # Create test member and booking
        member = Member(
            username='testuser', firstname='Test', lastname='User',
            email='test@test.com', status='Full'
        )
        db_session.add(member)
        db_session.commit()
        
        booking = Booking(
            booking_date=date.today() + timedelta(days=1),
            session=1,
            rink_count=2,
            organizer_id=member.id
        )
        db_session.add(booking)
        db_session.commit()
        
        # Create team and team member
        team = BookingTeam(
            booking_id=booking.id,
            team_name='Test Team'
        )
        db_session.add(team)
        db_session.commit()
        
        team_member = BookingTeamMember(
            team_id=team.id,
            member_id=member.id,
            position='Lead'
        )
        db_session.add(team_member)
        db_session.commit()
        
        booking_id = booking.id
        team_id = team.id
        team_member_id = team_member.id
        
        response = admin_client.delete(f'/bookings/api/v1/booking/{booking_id}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        
        # Verify cascading deletion
        assert db_session.get(Booking, booking_id) is None
        assert db_session.get(BookingTeam, team_id) is None
        assert db_session.get(BookingTeamMember, team_member_id) is None