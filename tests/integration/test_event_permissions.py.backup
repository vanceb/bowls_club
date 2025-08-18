"""
Integration tests for event-specific permission system.

Tests verify that:
1. Event-specific managers can fully manage their assigned events
2. Event-specific managers cannot access other events
3. Global Event Managers can access all events
4. Admin users can access all events
5. Regular users cannot access event management
"""
import pytest
from datetime import date, timedelta
from app.models import Member, Role, Pool, PoolRegistration, Booking


@pytest.fixture
def event_manager_role(db_session):
    """Create Event Manager role."""
    role = Role(name='Event Manager')
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def global_event_manager(db_session, event_manager_role):
    """Create a member with global Event Manager role."""
    member = Member(
        username='globaleventmgr',
        firstname='Global',
        lastname='EventManager',
        email='global.event@example.com',
        phone='555-0001',
        status='Full',
        joined_date=date.today()
    )
    member.set_password('password123')
    member.roles = [event_manager_role]
    db_session.add(member)
    db_session.commit()
    return member


@pytest.fixture
def specific_event_manager(db_session):
    """Create a regular member who will be assigned to specific events."""
    member = Member(
        username='specificeventmgr',
        firstname='Specific',
        lastname='EventManager',
        email='specific.event@example.com',
        phone='555-0002',  
        status='Full',
        joined_date=date.today()
    )
    member.set_password('password123')
    db_session.add(member)
    db_session.commit()
    return member


@pytest.fixture
def regular_member(db_session):
    """Create a regular member with no special permissions."""
    member = Member(
        username='regularmember',
        firstname='Regular',
        lastname='Member',
        email='regular@example.com',
        phone='555-0003',
        status='Full',
        joined_date=date.today()
    )
    member.set_password('password123')
    db_session.add(member)
    db_session.commit()
    return member


@pytest.fixture
def test_events(db_session):
    """Create test bookings (events)."""
    event1 = Booking(
        name='Test Event 1',
        booking_date=date.today() + timedelta(days=7),
        session=1,
        rink_count=2,
        event_type=1,  # Social
        gender=4,      # Open
        format=5,      # Fours - 2 Wood
        has_pool=False,
        booking_type='event'
    )
    
    event2 = Booking(
        name='Test Event 2',
        booking_date=date.today() + timedelta(days=14),
        session=1,
        rink_count=2,
        event_type=2,  # Competition
        gender=1,      # Men
        format=3,      # Pairs
        has_pool=True,
        booking_type='event'
    )
    
    event3 = Booking(
        name='Test Event 3',
        booking_date=date.today() + timedelta(days=21),
        session=1,
        rink_count=1,
        event_type=1,  # Social
        gender=2,      # Women
        format=1,      # Singles
        has_pool=False,
        booking_type='event'
    )
    
    db_session.add_all([event1, event2, event3])
    db_session.commit()
    
    return [event1, event2, event3]


@pytest.fixture
def assigned_events(db_session, test_events, specific_event_manager):
    """Assign specific event manager to event1 and event2, but not event3."""
    event1, event2, event3 = test_events
    
    # Assign specific_event_manager to event1 and event2
    event1.booking_managers.append(specific_event_manager)
    event2.booking_managers.append(specific_event_manager)
    # event3 is NOT assigned
    
    db_session.commit()
    return test_events


@pytest.fixture
def test_pool(db_session, test_events):
    """Create a pool for event2."""
    event2 = test_events[1]  # Second event has has_pool=True
    pool = Pool(
        booking_id=event2.id,
        is_open=True,
        max_players=16
    )
    db_session.add(pool)
    db_session.commit()
    return pool


@pytest.fixture
def pool_registrations(db_session, test_pool, regular_member):
    """Create pool registrations."""
    registration = PoolRegistration(
        pool_id=test_pool.id,
        member_id=regular_member.id,
        status='registered'
    )
    db_session.add(registration)
    db_session.commit()
    return [registration]


@pytest.fixture
def test_bookings(db_session, test_events):
    """Create test bookings for events."""
    event1, event2, event3 = test_events
    
    # Since Event model is removed, these are just the same booking objects
    # We don't need separate booking entities as bookings ARE the events now
    booking1 = event1  # Direct reference to the booking (which is now the event)
    booking2 = event2  # Direct reference to the booking (which is now the event)
    
    db_session.add_all([booking1, booking2])
    db_session.commit()
    return [booking1, booking2]


@pytest.fixture
def specific_manager_client(client, specific_event_manager):
    """Create authenticated client for specific event manager."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(specific_event_manager.id)
        sess['_fresh'] = True
    return client


@pytest.fixture
def global_manager_client(client, global_event_manager):
    """Create authenticated client for global event manager."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(global_event_manager.id)
        sess['_fresh'] = True
    return client


@pytest.fixture
def regular_client(client, regular_member):
    """Create authenticated client for regular member."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(regular_member.id)
        sess['_fresh'] = True
    return client


@pytest.mark.integration
class TestEventSpecificPermissions:
    """Test event-specific permission system."""
    
    def test_specific_manager_can_access_assigned_events(self, specific_manager_client, assigned_events):
        """Test that specific event managers can access their assigned events."""
        event1, event2, event3 = assigned_events
        
        # Should be able to access event1 (assigned)
        response = specific_manager_client.get(f'/events/manage/{event1.id}')
        assert response.status_code == 200
        assert event1.name.encode() in response.data
        
        # Should be able to access event2 (assigned)
        response = specific_manager_client.get(f'/events/manage/{event2.id}')
        assert response.status_code == 200
        assert event2.name.encode() in response.data
    
    def test_specific_manager_cannot_access_unassigned_events(self, specific_manager_client, assigned_events):
        """Test that specific event managers cannot access unassigned events."""
        event1, event2, event3 = assigned_events
        
        # Should NOT be able to access event3 (not assigned)
        response = specific_manager_client.get(f'/events/manage/{event3.id}', follow_redirects=True)
        # Should get access denied - either 403 or redirect with error message
        assert (response.status_code == 403 or 
                (response.status_code == 200 and b'You do not have permission to manage this event.' in response.data))
    
    def test_global_manager_can_access_all_events(self, global_manager_client, assigned_events):
        """Test that global Event Managers can access all events."""
        event1, event2, event3 = assigned_events
        
        # Should be able to access all events
        for event in [event1, event2, event3]:
            response = global_manager_client.get(f'/events/manage/{event.id}')
            assert response.status_code == 200
            assert event.name.encode() in response.data
    
    def test_admin_can_access_all_events(self, admin_client, assigned_events):
        """Test that admin users can access all events."""
        event1, event2, event3 = assigned_events
        
        # Should be able to access all events
        for event in [event1, event2, event3]:
            response = admin_client.get(f'/events/manage/{event.id}')
            assert response.status_code == 200
            assert event.name.encode() in response.data
    
    def test_regular_member_cannot_access_event_management(self, regular_client, assigned_events):
        """Test that regular members cannot access event management."""
        event1, event2, event3 = assigned_events
        
        # Should not be able to access any event management
        for event in [event1, event2, event3]:
            response = regular_client.get(f'/events/manage/{event.id}')
            assert response.status_code == 302  # Redirect due to role requirement


@pytest.mark.integration  
class TestEventPoolPermissions:
    """Test event-specific permissions for pool management."""
    
    def test_specific_manager_cannot_access_admin_pool_routes(self, specific_manager_client, assigned_events, test_pool):
        """Test that specific managers cannot access admin pool routes (Approach 2: only global managers can use admin routes)."""
        event1, event2, event3 = assigned_events
        
        # Should NOT be able to access admin pool toggle route (requires Event Manager role)
        response = specific_manager_client.post(
            f'/admin/toggle_event_pool/{event2.id}',
            data={}
        )
        # Should get 403 Forbidden due to role requirement
        assert response.status_code == 403
    
    def test_global_manager_can_access_admin_pool_routes(self, global_manager_client, assigned_events, test_pool):
        """Test that global managers can access admin pool routes."""
        event1, event2, event3 = assigned_events
        
        # Should be able to access admin pool toggle route (has Event Manager role)
        # Don't follow redirects to avoid template errors unrelated to permission testing
        response = global_manager_client.post(
            f'/admin/toggle_event_pool/{event2.id}',
            data={}
        )
        # Should get redirect (not 403 permission denied) - means role check passed
        assert response.status_code == 302  # Redirect on success
        # Should NOT get forbidden due to role check
        assert response.status_code != 403
    
    def test_specific_manager_can_use_event_pool_toggle(self, specific_manager_client, assigned_events, test_pool):
        """Test that specific managers can use event-specific pool toggle route."""
        event1, event2, event3 = assigned_events
        
        # Should be able to use event-specific pool toggle for assigned event
        response = specific_manager_client.post(
            f'/events/toggle_pool/{event2.id}',
            data={},
            follow_redirects=True
        )
        # Should get CSRF error (not permission denied) - means event permission check passed
        assert response.status_code == 200
        assert (b'Security validation failed' in response.data or 
                b'Pool' in response.data)
        # Should NOT get event permission denied
        assert b'You do not have permission to manage this event.' not in response.data
    
    def test_specific_manager_cannot_use_event_pool_toggle_unassigned(self, specific_manager_client, assigned_events):
        """Test that specific managers cannot use pool toggle for unassigned events.""" 
        event1, event2, event3 = assigned_events
        
        # Should NOT be able to use pool toggle for unassigned event (event3)
        # This will redirect to /events/ after failing permission check, which requires Event Manager role
        response = specific_manager_client.post(
            f'/events/toggle_pool/{event3.id}',
            data={},
            follow_redirects=True
        )
        # Should get 403 due to redirect to events list page that requires Event Manager role
        assert response.status_code == 403


@pytest.mark.integration
class TestEventBookingPermissions:
    """Test event-specific permissions for booking management."""
    
    def test_specific_manager_cannot_access_admin_booking_routes(self, specific_manager_client, assigned_events, test_bookings):
        """Test that specific managers cannot access admin booking routes (Approach 2: only global managers can use admin routes)."""
        event1, event2, event3 = assigned_events
        booking1, booking2 = test_bookings
        
        # Should NOT be able to access admin booking edit route (requires Event Manager role)
        response = specific_manager_client.get(f'/bookings/admin/edit/{booking1.id}')
        # Should get 403 Forbidden due to role requirement
        assert response.status_code == 403
    
    def test_global_manager_can_edit_all_event_bookings(self, global_manager_client, assigned_events, test_bookings):
        """Test that global managers can edit all event bookings."""
        event1, event2, event3 = assigned_events
        booking1, booking2 = test_bookings
        
        # Should be able to edit all bookings
        for booking in [booking1, booking2]:
            response = global_manager_client.get(f'/bookings/admin/edit/{booking.id}')
            assert response.status_code == 200
            assert b'Edit Booking' in response.data or booking.name.encode() in response.data


@pytest.mark.integration
class TestEventManagerAssignment:
    """Test event manager assignment functionality."""
    
    def test_add_event_manager_to_event(self, global_manager_client, assigned_events, regular_member):
        """Test adding a new event manager to an event."""
        event1, event2, event3 = assigned_events
        
        # Add regular_member as manager to event3
        response = global_manager_client.post(
            f'/events/manage/{event3.id}',
            data={
                'csrf_token': 'test-token',
                'action': 'add_manager',
                'member_id': regular_member.id
            },
            follow_redirects=True
        )
        # Check that it's not blocked by permissions
        assert response.status_code == 200
        assert (b'Security validation failed' in response.data or 
                b'has been added as an event manager' in response.data or
                b'Event Managers' in response.data)
    
    def test_remove_event_manager_from_event(self, global_manager_client, assigned_events, specific_event_manager):
        """Test removing an event manager from an event."""
        event1, event2, event3 = assigned_events
        
        # Remove specific_event_manager from event1
        response = global_manager_client.post(
            f'/events/manage/{event1.id}',
            data={
                'csrf_token': 'test-token',
                'action': 'remove_manager',
                'member_id': specific_event_manager.id
            },
            follow_redirects=True
        )
        # Check that it's not blocked by permissions
        assert response.status_code == 200
        assert (b'Security validation failed' in response.data or 
                b'has been removed as an event manager' in response.data or
                b'Event Managers' in response.data)
    
    def test_specific_manager_can_assign_managers_to_assigned_event(self, specific_manager_client, assigned_events, regular_member):
        """Test that specific managers can assign other managers to their assigned events."""
        event1, event2, event3 = assigned_events
        
        # Should be able to add manager to assigned event (event1)
        response = specific_manager_client.post(
            f'/events/manage/{event1.id}',
            data={
                'csrf_token': 'test-token',
                'action': 'add_manager',
                'member_id': regular_member.id
            },
            follow_redirects=True
        )
        assert response.status_code == 200
        # Should not get permission denied
        assert b'You do not have permission to manage this event.' not in response.data
    
    def test_specific_manager_cannot_assign_managers_to_unassigned_event(self, specific_manager_client, assigned_events, regular_member):
        """Test that specific managers cannot assign managers to unassigned events."""
        event1, event2, event3 = assigned_events
        
        # Should NOT be able to add manager to unassigned event (event3)
        response = specific_manager_client.post(
            f'/events/manage/{event3.id}',
            data={
                'action': 'add_manager',
                'member_id': regular_member.id
            },
            follow_redirects=True
        )
        # Should get access denied (either 403 or error message)
        assert (response.status_code == 403 or 
                (response.status_code == 200 and b'You do not have permission to manage this event.' in response.data))


@pytest.mark.integration
class TestEventListAccess:
    """Test access to event listing and creation."""
    
    def test_global_manager_can_access_event_list(self, global_manager_client):
        """Test that global Event Managers can access event list."""
        response = global_manager_client.get('/events/')
        assert response.status_code == 200
        assert b'Events' in response.data or b'List' in response.data
    
    def test_global_manager_can_create_events(self, global_manager_client):
        """Test that global Event Managers can create new events."""
        response = global_manager_client.get('/events/create')
        assert response.status_code == 200
        assert b'Create' in response.data or b'Event' in response.data
    
    def test_specific_manager_cannot_access_event_list(self, specific_manager_client):
        """Test that specific event managers cannot access general event list (security: only global managers can)."""
        response = specific_manager_client.get('/events/')
        assert response.status_code == 403  # Access denied due to role requirement
    
    def test_specific_manager_cannot_create_events(self, specific_manager_client):
        """Test that specific event managers cannot create new events (security: only global managers can)."""
        response = specific_manager_client.get('/events/create')
        assert response.status_code == 403  # Access denied due to role requirement
    
    def test_regular_member_cannot_access_event_management(self, regular_client):
        """Test that regular members cannot access event management routes."""
        # Cannot access event list
        response = regular_client.get('/events/')
        assert response.status_code == 403  # Access denied due to role requirement
        
        # Cannot access event creation
        response = regular_client.get('/events/create') 
        assert response.status_code == 403  # Access denied due to role requirement


@pytest.mark.integration
class TestApiPermissions:
    """Test API endpoint permissions."""
    
    def test_specific_manager_can_access_assigned_event_api(self, specific_manager_client, assigned_events):
        """Test that specific managers can access API for assigned events."""
        event1, event2, event3 = assigned_events
        
        # Should be able to access API for assigned event
        response = specific_manager_client.get(f'/events/api/v1/event/{event1.id}')
        assert response.status_code == 200
        # Should return JSON with event data
        data = response.get_json()
        assert data is not None
        assert data.get('success') is True or data.get('event') is not None
    
    def test_specific_manager_cannot_access_unassigned_event_api(self, specific_manager_client, assigned_events):
        """Test that specific managers cannot access API for unassigned events."""
        event1, event2, event3 = assigned_events
        
        # Should NOT be able to access API for unassigned event
        response = specific_manager_client.get(f'/events/api/v1/event/{event3.id}')
        assert response.status_code == 403  # Forbidden
        data = response.get_json()
        assert data is not None
        assert data.get('success') is False
        assert 'Permission denied' in data.get('error', '')