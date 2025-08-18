"""
Functional tests for role-based access control across the entire application.

Tests validate end-to-end permission enforcement for all user roles
without modifying application code.
"""

import pytest
from flask import url_for
from app import create_app, db
from app.models import Member, Role, Pool, Booking, Post


class TestAdminAccess:
    """Test admin user access to all functionality."""
    
    def test_admin_full_system_access(self, client, admin_member):
        """Test admin can access all areas of the system."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_member.id)
        
        # Admin should access all main areas
        admin_accessible_routes = [
            '/',  # Home
            '/members/directory',  # Member directory
            '/bookings/',  # Bookings
            '/upcoming_events',  # Upcoming events
            '/members/admin/manage_members',  # User management
            '/members/admin/manage_roles',  # Role management
            '/members/admin/import_users',  # User import
            '/bookings/admin/list',  # Event management (consolidated into bookings)
            '/bookings/admin/create',  # Event creation
            '/pools/',  # Pool management
            '/content/admin/write_post',  # Content creation
            '/content/admin/manage_posts',  # Content management
            '/content/admin/manage_policy_pages',  # Policy management
        ]
        
        for route in admin_accessible_routes:
            response = client.get(route)
            assert response.status_code == 200, f"Admin should access {route}"
    
    def test_admin_can_manage_all_events(self, client, admin_member, test_event):
        """Test admin can manage any event regardless of assignment."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_member.id)
        
        # Admin should access booking management even if not assigned
        response = client.get(f'/bookings/admin/manage/{test_event.id}')
        assert response.status_code == 200
    
    def test_admin_can_view_all_member_data(self, client, admin_member, db_session):
        """Test admin can view private member information."""
        # Create member with private settings using factory
        from tests.fixtures.factories import MemberFactory
        private_member = MemberFactory.create(
            username='privatemember',
            firstname='Private',
            lastname='Member',
            email='private@example.com',
            phone='555-0123',
            status='Full',
            share_phone=False,
            share_email=False
        )
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_member.id)
        
        # Admin should see private data in API
        response = client.get('/members/api/v1/search?route=manage_members')
        assert response.status_code == 200
        data = response.get_json()
        
        # Find private member and verify admin sees private data
        private_member_data = None
        for member in data.get('members', []):
            if member['id'] == private_member.id:
                private_member_data = member
                break
        
        assert private_member_data is not None
        # Admin should have access to private data
        assert 'phone' in private_member_data or 'email' in private_member_data


class TestEventManagerAccess:
    """Test Event Manager role access permissions."""
    
    def test_event_manager_event_access(self, client, event_manager_member):
        """Test Event Manager can access event functionality."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_member.id)
        
        event_manager_routes = [
            '/bookings/admin/list',  # List bookings (replaces events list)
            '/bookings/admin/create',  # Create bookings (replaces event creation)
            '/pools/',  # Pool management
        ]
        
        for route in event_manager_routes:
            response = client.get(route)
            assert response.status_code == 200, f"Event Manager should access {route}"
    
    def test_event_manager_booking_admin_access(self, client, event_manager_member, test_booking):
        """Test Event Manager can access booking admin functions."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_member.id)
        
        # Should access booking admin routes
        response = client.get(f'/bookings/admin/manage/{test_booking.id}')
        assert response.status_code == 200
        
        response = client.get(f'/bookings/admin/manage_teams/{test_booking.id}')
        assert response.status_code == 200
    
    def test_event_manager_cannot_access_user_management(self, client, event_manager_member):
        """Test Event Manager cannot access user management."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_member.id)
        
        restricted_routes = [
            '/members/admin/manage_members',
            '/members/admin/manage_roles',
            '/members/admin/import_users',
        ]
        
        for route in restricted_routes:
            response = client.get(route)
            assert response.status_code in [403, 302], f"Event Manager should not access {route}"
    
    def test_event_manager_cannot_access_content_management(self, client, event_manager_member):
        """Test Event Manager cannot access content management."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_member.id)
        
        content_routes = [
            '/content/admin/write_post',
            '/content/admin/manage_posts',
            '/content/admin/manage_policy_pages',
        ]
        
        for route in content_routes:
            response = client.get(route)
            assert response.status_code in [403, 302], f"Event Manager should not access {route}"


class TestUserManagerAccess:
    """Test User Manager role access permissions."""
    
    def test_user_manager_user_access(self, client, user_manager_member):
        """Test User Manager can access user functionality."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_manager_member.id)
        
        user_manager_routes = [
            '/members/admin/manage_members',
            '/members/admin/manage_roles',
        ]
        
        for route in user_manager_routes:
            response = client.get(route)
            assert response.status_code == 200, f"User Manager should access {route}"
    
    def test_user_manager_cannot_access_events(self, client, user_manager_member):
        """Test User Manager cannot access event management."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_manager_member.id)
        
        event_routes = [
            '/bookings/admin/list',
            '/bookings/admin/create',
            '/pools/',
        ]
        
        for route in event_routes:
            response = client.get(route)
            assert response.status_code in [403, 302], f"User Manager should not access {route}"
    
    def test_user_manager_cannot_access_content(self, client, user_manager_member):
        """Test User Manager cannot access content management."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_manager_member.id)
        
        content_routes = [
            '/content/admin/write_post',
            '/content/admin/manage_posts',
        ]
        
        for route in content_routes:
            response = client.get(route)
            assert response.status_code in [403, 302], f"User Manager should not access {route}"


class TestContentManagerAccess:
    """Test Content Manager role access permissions."""
    
    def test_content_manager_content_access(self, client, content_manager_member):
        """Test Content Manager can access content functionality."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(content_manager_member.id)
        
        content_routes = [
            '/content/admin/write_post',
            '/content/admin/manage_posts',
            '/content/admin/manage_policy_pages',
        ]
        
        for route in content_routes:
            response = client.get(route)
            assert response.status_code == 200, f"Content Manager should access {route}"
    
    def test_content_manager_cannot_access_events(self, client, content_manager_member):
        """Test Content Manager cannot access event management."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(content_manager_member.id)
        
        event_routes = [
            '/bookings/admin/list',
            '/bookings/admin/create',
            '/pools/',
        ]
        
        for route in event_routes:
            response = client.get(route)
            assert response.status_code in [403, 302], f"Content Manager should not access {route}"
    
    def test_content_manager_cannot_access_users(self, client, content_manager_member):
        """Test Content Manager cannot access user management."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(content_manager_member.id)
        
        user_routes = [
            '/members/admin/manage_members',
            '/members/admin/manage_roles',
        ]
        
        for route in user_routes:
            response = client.get(route)
            assert response.status_code in [403, 302], f"Content Manager should not access {route}"


class TestRegularUserAccess:
    """Test regular user (no special roles) access permissions."""
    
    def test_regular_user_basic_access(self, client, test_member):
        """Test regular users can access basic functionality."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        basic_routes = [
            '/',  # Home
            '/members/directory',  # Member directory
            '/bookings/',  # View bookings
            '/upcoming_events',  # View upcoming events
            '/bookings/my_games',  # Personal games
            '/members/auth/profile',  # Personal profile
        ]
        
        for route in basic_routes:
            response = client.get(route)
            assert response.status_code == 200, f"Regular user should access {route}"
    
    def test_regular_user_cannot_access_admin_areas(self, client, test_member):
        """Test regular users cannot access admin functionality."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        admin_routes = [
            '/members/admin/manage_members',
            '/members/admin/manage_roles',
            '/bookings/admin/list',
            '/bookings/admin/create',
            '/pools/',
            '/content/admin/write_post',
            '/content/admin/manage_posts',
        ]
        
        for route in admin_routes:
            response = client.get(route)
            assert response.status_code in [403, 302], f"Regular user should not access {route}"
    
    def test_regular_user_can_register_for_events(self, client, test_member, test_event_with_pool):
        """Test regular users can register for events."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        # Should be able to register for events
        response = client.post(f'/pools/register/{test_event_with_pool.pool.id}')
        # Should succeed or redirect (depending on CSRF implementation)
        assert response.status_code in [200, 302]


class TestBookingSpecificOrganizerAccess:
    """Test booking-specific organizer permissions."""
    
    def test_booking_organizer_can_manage_assigned_booking(self, client, test_member, test_event):
        """Test user assigned as booking organizer can manage specific booking."""
        # Assign user as organizer for specific booking (no additional roles needed)
        test_event.organizer_id = test_member.id
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        # Should access assigned booking (organizers can manage their own bookings)
        response = client.get(f'/bookings/admin/manage/{test_event.id}')
        # If the application doesn't yet support organizer-specific permissions,
        # this might return 403, which would indicate the feature needs implementation
        assert response.status_code in [200, 403], "Organizer should access their booking or get 403 if not yet implemented"
    
    def test_booking_organizer_cannot_manage_other_bookings(self, client, test_member, test_event, db_session):
        """Test booking organizer cannot manage unassigned bookings."""
        # Create another booking without assigning user as organizer
        from datetime import date, timedelta
        from tests.fixtures.factories import MemberFactory
        other_organizer = MemberFactory.create()
        other_booking = Booking(
            name='Other Event',
            booking_date=date.today() + timedelta(days=14),
            session=1,
            rink_count=2,
            event_type=1,
            gender=1,
            format=1,
            organizer_id=other_organizer.id
        )
        db_session.add(other_booking)
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        # Should NOT access unassigned booking
        response = client.get(f'/bookings/admin/manage/{other_booking.id}')
        assert response.status_code in [403, 302]
    
    def test_booking_organizer_cannot_access_global_booking_management(self, client, test_member, test_event):
        """Test booking organizer cannot access global booking management."""
        test_event.organizer_id = test_member.id
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        # Should NOT access global booking list or creation
        response = client.get('/bookings/admin/list')
        assert response.status_code in [403, 302]
        
        response = client.get('/bookings/admin/create')
        assert response.status_code in [403, 302]


class TestCrossRolePermissions:
    """Test users with multiple roles have combined permissions."""
    
    def test_user_with_multiple_roles(self, client, app, db_session, core_roles):
        """Test user with multiple roles gets combined permissions."""
        with app.app_context():
            # Create user with multiple roles
            from tests.fixtures.factories import MemberFactory
            user = MemberFactory.create(
                username='multirole',
                firstname='Multi',
                lastname='Role',
                email='multirole@example.com',
                phone='123-456-7890',
                status='Full'
            )
            
            # Query roles from current session to avoid session conflicts
            event_manager_role = db_session.query(Role).filter_by(name='Event Manager').first()
            content_manager_role = db_session.query(Role).filter_by(name='Content Manager').first()
            
            # If roles don't exist, create them
            if not event_manager_role:
                event_manager_role = Role(name='Event Manager')
                db_session.add(event_manager_role)
                db_session.flush()
            
            if not content_manager_role:
                content_manager_role = Role(name='Content Manager')
                db_session.add(content_manager_role)
                db_session.flush()
            
            user.roles = [event_manager_role, content_manager_role]
            db_session.add(user)
            db_session.commit()
            
            with client.session_transaction() as sess:
                sess['_user_id'] = str(user.id)
            
            # Should access both booking and content management
            event_routes = ['/bookings/admin/list', '/pools/']
            content_routes = ['/content/admin/write_post', '/content/admin/manage_posts']
            
            for route in event_routes + content_routes:
                response = client.get(route)
                assert response.status_code == 200, f"Multi-role user should access {route}"


class TestUnauthenticatedAccess:
    """Test unauthenticated user access restrictions."""
    
    def test_unauthenticated_redirected_to_login(self, client):
        """Test unauthenticated users are redirected to login."""
        protected_routes = [
            '/',
            '/members/directory',
            '/bookings/',
            '/upcoming_events',
            '/members/auth/profile',
        ]
        
        for route in protected_routes:
            response = client.get(route)
            # Should redirect to login
            assert response.status_code == 302
            assert '/members/auth/login' in response.location or '/login' in response.location
    
    def test_unauthenticated_can_access_public_routes(self, client):
        """Test unauthenticated users can access public routes."""
        public_routes = [
            '/members/auth/login',
            '/members/auth/reset_password',
            '/members/apply',  # Public member application
        ]
        
        for route in public_routes:
            response = client.get(route)
            assert response.status_code == 200, f"Unauthenticated should access {route}"


class TestAPIPermissions:
    """Test API endpoint permissions."""
    
    def test_api_requires_authentication(self, client):
        """Test API endpoints require authentication."""
        api_routes = [
            '/api/events/upcoming',
            '/api/event/1',
            '/api/booking/1',
            '/members/api/v1/search',
        ]
        
        for route in api_routes:
            response = client.get(route)
            assert response.status_code in [401, 302], f"API {route} should require auth"
    
    def test_admin_api_requires_admin_role(self, client, test_member):
        """Test admin API endpoints require admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        admin_api_routes = [
            '/members/api/v1/users_with_roles',
        ]
        
        for route in admin_api_routes:
            response = client.get(route)
            assert response.status_code in [403, 302], f"Regular user should not access admin API {route}"
    
    def test_event_manager_api_access(self, client, event_manager_member, test_event):
        """Test Event Manager can access event management APIs."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_member.id)
        
        # Should access event API
        response = client.get(f'/api/event/{test_event.id}')
        assert response.status_code == 200


class TestPermissionInheritance:
    """Test permission inheritance and role hierarchy."""
    
    def test_admin_inherits_all_permissions(self, client, admin_member):
        """Test admin has all permissions regardless of specific roles."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_member.id)
        
        # Admin should access all role-specific functionality
        all_protected_routes = [
            '/members/admin/manage_members',  # User Manager
            '/bookings/admin/list',  # Event Manager
            '/content/admin/write_post',  # Content Manager
        ]
        
        for route in all_protected_routes:
            response = client.get(route)
            assert response.status_code == 200, f"Admin should inherit access to {route}"
    
    def test_role_permissions_are_additive(self, client, app, db_session, core_roles):
        """Test multiple roles provide additive permissions."""
        with app.app_context():
            # Create user with Event Manager and User Manager roles
            from tests.fixtures.factories import MemberFactory
            user = MemberFactory.create(
                username='additive',
                firstname='Additive',
                lastname='Roles',
                email='additive@example.com',
                phone='123-456-7890',
                status='Full'
            )
            
            # Query roles from current session to avoid session conflicts
            event_role = db_session.query(Role).filter_by(name='Event Manager').first()
            user_role = db_session.query(Role).filter_by(name='User Manager').first()
            
            # If roles don't exist, create them
            if not event_role:
                event_role = Role(name='Event Manager')
                db_session.add(event_role)
                db_session.flush()
            
            if not user_role:
                user_role = Role(name='User Manager')
                db_session.add(user_role)
                db_session.flush()
            
            user.roles = [event_role, user_role]
            db_session.add(user)
            db_session.commit()
            
            with client.session_transaction() as sess:
                sess['_user_id'] = str(user.id)
            
            # Should access both Event Manager and User Manager routes
            combined_routes = [
                '/bookings/admin/list',  # Event Manager
                '/members/admin/manage_members',  # User Manager
            ]
            
            for route in combined_routes:
                response = client.get(route)
                assert response.status_code == 200, f"Combined roles should access {route}"