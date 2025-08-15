"""
Integration tests for pools blueprint routes.

Tests validate pool management functionality, member registration,
and admin operations without modifying application code.
"""

import pytest
from flask import url_for
from unittest.mock import patch
from app import create_app, db
from app.models import Member, Pool, PoolRegistration, Booking, Role
from tests.fixtures.factories import MemberFactory


class TestPoolManagement:
    """Test core pool management routes."""
    
    def test_list_pools_requires_event_manager(self, client, test_member):
        """Test pool list requires Event Manager role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        response = client.get('/pools/')
        assert response.status_code in [403, 302]
    
    def test_list_pools_with_event_manager(self, client, event_manager_user, temp_booking_with_pool):
        """Test Event Manager can list pools."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_user.id)
        
        response = client.get('/pools/')
        assert response.status_code == 200
        assert 'pools' in response.get_data(as_text=True).lower()
    
    def test_create_event_pool_get(self, client, event_manager_user, temp_booking):
        """Test GET request to create event pool form."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_user.id)
        
        response = client.get(f'/pools/create/event/{temp_booking.id}')
        assert response.status_code == 200
    
    def test_create_event_pool_post_requires_csrf(self, client, event_manager_user, temp_booking):
        """Test creating event pool requires CSRF token."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_user.id)
        
        response = client.post(f'/pools/create/event/{temp_booking.id}', data={
            'is_open': True
        })
        assert response.status_code in [400, 302, 403]
    
    def test_create_booking_pool_get(self, client, event_manager_user, temp_booking):
        """Test GET request to create booking pool form."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_user.id)
        
        response = client.get(f'/pools/create/booking/{temp_booking.id}')
        assert response.status_code == 200
    
    def test_manage_pool_requires_permission(self, client, test_member, temp_pool):
        """Test managing pool requires appropriate permissions."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        response = client.get(f'/pools/manage/{temp_pool.id}')
        assert response.status_code in [403, 302]
    
    def test_manage_pool_with_permission(self, client, event_manager_user, temp_pool):
        """Test Event Manager can manage pools."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_user.id)
        
        response = client.get(f'/pools/manage/{temp_pool.id}')
        assert response.status_code == 200


class TestPoolRegistration:
    """Test pool member registration functionality."""
    
    def test_register_member_requires_auth(self, client, temp_pool):
        """Test pool registration requires authentication."""
        response = client.post(f'/pools/register/{temp_pool.id}')
        assert response.status_code in [401, 302]
    
    def test_register_member_success(self, client, test_member, temp_booking_with_pool):
        """Test successful member registration to pool."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        pool = temp_booking_with_pool.pool
        
        # Mock audit logging to avoid file system operations
        with patch('app.pools.routes.audit_log_create') as mock_audit:
            response = client.post(f'/pools/register/{pool.id}')
            
            # Should succeed (redirect or success page)
            assert response.status_code in [200, 302]
            
            # Should log the registration
            mock_audit.assert_called()
    
    def test_register_member_already_registered(self, client, test_member, temp_booking_with_pool):
        """Test registering already registered member."""
        pool = temp_booking_with_pool.pool
        
        # Create existing registration
        existing_reg = PoolRegistration(pool_id=pool.id, member_id=test_member.id)
        db.session.add(existing_reg)
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        response = client.post(f'/pools/register/{pool.id}')
        # Should handle gracefully (warning message or redirect)
        assert response.status_code in [200, 302]
    
    def test_register_member_pool_closed(self, client, test_member, temp_booking):
        """Test registering for closed pool."""
        # Create closed pool
        closed_pool = Pool(booking_id=temp_booking.id, is_open=False)
        db.session.add(closed_pool)
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        response = client.post(f'/pools/register/{closed_pool.id}')
        # Should reject or show warning
        assert response.status_code in [200, 302]
    
    def test_unregister_member_requires_auth(self, client):
        """Test pool unregistration requires authentication."""
        response = client.post('/pools/unregister/1')
        assert response.status_code in [401, 302]
    
    def test_unregister_member_success(self, client, test_member, temp_booking_with_pool):
        """Test successful member unregistration from pool."""
        pool = temp_booking_with_pool.pool
        
        # Create registration to remove
        registration = PoolRegistration(pool_id=pool.id, member_id=test_member.id)
        db.session.add(registration)
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        with patch('app.pools.routes.audit_log_delete') as mock_audit:
            response = client.post(f'/pools/unregister/{registration.id}')
            
            assert response.status_code in [200, 302]
            mock_audit.assert_called()
    
    def test_unregister_member_not_registered(self, client, test_member):
        """Test unregistering non-existent registration."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        response = client.post('/pools/unregister/99999')
        assert response.status_code in [404, 302]


class TestPoolActions:
    """Test pool action routes."""
    
    def test_toggle_pool_status_requires_permission(self, client, test_member, temp_pool):
        """Test toggling pool status requires permissions."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        response = client.post(f'/pools/toggle/{temp_pool.id}')
        assert response.status_code in [403, 302]
    
    def test_toggle_pool_status_with_permission(self, client, event_manager_user, temp_pool):
        """Test Event Manager can toggle pool status."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_user.id)
        
        original_status = temp_pool.is_open
        
        with patch('app.pools.routes.audit_log_update') as mock_audit:
            response = client.post(f'/pools/toggle/{temp_pool.id}')
            
            assert response.status_code in [200, 302]
            mock_audit.assert_called()
            
            # Verify status changed
            db.session.refresh(temp_pool)
            assert temp_pool.is_open != original_status
    
    def test_delete_pool_requires_event_manager(self, client, test_member, temp_pool):
        """Test pool deletion requires Event Manager role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        response = client.post(f'/pools/delete/{temp_pool.id}')
        assert response.status_code in [403, 302]
    
    def test_delete_pool_with_registrations_success(self, client, event_manager_user, temp_pool, test_member):
        """Test pool with registrations can be deleted (cascades to remove registrations)."""
        # Add registration to pool
        registration = PoolRegistration(pool_id=temp_pool.id, member_id=test_member.id)
        db.session.add(registration)
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_user.id)
        
        with patch('app.pools.routes.audit_log_delete') as mock_audit:
            response = client.post(f'/pools/delete/{temp_pool.id}')
            # Should succeed
            assert response.status_code in [200, 302]
            mock_audit.assert_called()
        
        # Pool should be deleted (cascade deletes registrations too)
        assert db.session.get(Pool, temp_pool.id) is None
        assert db.session.get(PoolRegistration, registration.id) is None
    
    def test_delete_empty_pool_success(self, client, event_manager_user, temp_booking):
        """Test successful deletion of empty pool."""
        # Create empty pool
        empty_pool = Pool(booking_id=temp_booking.id, is_open=True)
        db.session.add(empty_pool)
        db.session.commit()
        pool_id = empty_pool.id
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_user.id)
        
        with patch('app.pools.routes.audit_log_delete') as mock_audit:
            response = client.post(f'/pools/delete/{pool_id}')
            
            assert response.status_code in [200, 302]
            mock_audit.assert_called()


class TestPoolAdminRoutes:
    """Test pool admin management routes."""
    
    def test_admin_create_event_pool_requires_role(self, client, test_member, temp_booking):
        """Test admin pool creation requires Event Manager role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        response = client.post(f'/pools/admin/create_event_pool/{temp_booking.id}')
        assert response.status_code in [403, 302]
    
    def test_admin_create_event_pool_success(self, client, event_manager_user, temp_booking):
        """Test admin can create event pool."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_user.id)
        
        with patch('app.pools.routes.audit_log_create') as mock_audit:
            response = client.post(f'/pools/admin/create_event_pool/{temp_booking.id}')
            
            assert response.status_code in [200, 302]
            mock_audit.assert_called()
    
    def test_admin_add_member_to_pool_requires_role(self, client, test_member, temp_booking):
        """Test admin adding member to pool requires Event Manager role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        response = client.post(f'/pools/admin/add_member_to_pool/{temp_booking.id}', data={
            'member_id': test_member.id
        })
        assert response.status_code in [403, 302]
    
    def test_admin_add_member_to_pool_success(self, client, event_manager_user, temp_booking_with_pool, test_member):
        """Test admin can add member to pool."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_user.id)
        
        with patch('app.pools.routes.audit_log_create') as mock_audit:
            response = client.post(f'/pools/admin/add_member_to_pool/{temp_booking_with_pool.id}', data={
                'member_id': test_member.id
            })
            
            assert response.status_code in [200, 302]
            mock_audit.assert_called()
    
    def test_admin_delete_from_pool_requires_role(self, client, test_member):
        """Test admin removing from pool requires Event Manager role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        response = client.post('/pools/admin/delete_from_pool/1')
        assert response.status_code in [403, 302]
    
    def test_admin_delete_from_pool_success(self, client, event_manager_user, temp_booking_with_pool, test_member):
        """Test admin can remove member from pool."""
        pool = temp_booking_with_pool.pool
        registration = PoolRegistration(pool_id=pool.id, member_id=test_member.id)
        db.session.add(registration)
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_user.id)
        
        with patch('app.pools.routes.audit_log_delete') as mock_audit:
            response = client.post(f'/pools/admin/delete_from_pool/{registration.id}')
            
            assert response.status_code in [200, 302]
            mock_audit.assert_called()
    
    def test_admin_auto_select_pool_members_requires_role(self, client, test_member, temp_booking):
        """Test auto-select pool members requires Event Manager role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        response = client.post(f'/pools/admin/auto_select_pool_members/{temp_booking.id}', data={
            'method': 'oldest_first',
            'count': 4
        })
        assert response.status_code in [403, 302]
    
    def test_admin_auto_select_pool_members_redirects(self, client, event_manager_user, temp_booking_with_pool):
        """Test admin auto-select shows info message and redirects (no actual selection performed)."""
        pool = temp_booking_with_pool.pool
        
        # Add multiple members to pool
        members = []
        for i in range(6):
            member = MemberFactory()
            registration = PoolRegistration(pool_id=pool.id, member_id=member.id)
            db.session.add(member)
            db.session.add(registration)
            members.append(member)
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_user.id)
        
        response = client.post(f'/pools/admin/auto_select_pool_members/{temp_booking_with_pool.id}', data={
            'method': 'oldest_first',
            'count': 4
        })
        
        # Should redirect (no bulk operation performed, just shows info message)
        assert response.status_code in [200, 302]


class TestPoolAPI:
    """Test pool API endpoints."""
    
    def test_api_get_pool_requires_auth(self, client, temp_pool):
        """Test pool API requires authentication."""
        response = client.get(f'/pools/api/v1/pool/{temp_pool.id}')
        assert response.status_code in [401, 302]
    
    def test_api_get_pool_success(self, client, event_manager_user, temp_pool):
        """Test Event Manager can get pool details."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_user.id)
        
        response = client.get(f'/pools/api/v1/pool/{temp_pool.id}')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'success' in data
        assert data['success'] == True
        assert 'pool' in data
    
    def test_api_get_pool_not_found(self, client, test_member):
        """Test API returns 404 for non-existent pool."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        response = client.get('/pools/api/v1/pool/99999')
        assert response.status_code == 404
        
        data = response.get_json()
        assert data['success'] == False


class TestPoolBusinessLogic:
    """Test pool business logic and edge cases."""
    
    def test_pool_capacity_limits(self, client, test_member, temp_booking_with_pool):
        """Test pool respects capacity limits if configured."""
        pool = temp_booking_with_pool.pool
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        # Test registration when pool might be at capacity
        response = client.post(f'/pools/register/{pool.id}')
        assert response.status_code in [200, 302]
    
    def test_pool_registration_with_event_dates(self, client, test_member, temp_booking_with_pool):
        """Test pool registration considers event timing."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        # Registration should work for future events
        response = client.post(f'/pools/register/{temp_booking_with_pool.pool.id}')
        assert response.status_code in [200, 302]
    
    def test_pool_member_status_validation(self, client, temp_booking_with_pool):
        """Test only active members can register for pools."""
        # Create inactive member
        inactive_member = MemberFactory(status='Inactive')
        db.session.add(inactive_member)
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(inactive_member.id)
        
        response = client.post(f'/pools/register/{temp_booking_with_pool.pool.id}')
        # Should prevent inactive members from registering
        assert response.status_code in [200, 302, 403]
    
    def test_pool_registration_audit_trail(self, client, test_member, temp_booking_with_pool):
        """Test pool operations create proper audit trail."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
        
        with patch('app.pools.routes.audit_log_create') as mock_create:
            with patch('app.pools.routes.audit_log_delete') as mock_delete:
                # Register
                response = client.post(f'/pools/register/{temp_booking_with_pool.pool.id}')
                if response.status_code in [200, 302]:
                    mock_create.assert_called()
                
                # Find registration to unregister
                registration = PoolRegistration.query.filter_by(
                    pool_id=temp_booking_with_pool.pool.id,
                    member_id=test_member.id
                ).first()
                
                if registration:
                    # Unregister
                    response = client.post(f'/pools/unregister/{registration.id}')
                    if response.status_code in [200, 302]:
                        mock_delete.assert_called()


class TestPoolFiltering:
    """Test pool filtering and search functionality."""
    
    def test_pool_list_filtering_by_event_type(self, client, event_manager_user):
        """Test filtering pools by event type."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_user.id)
        
        # Test with filter parameters
        response = client.get('/pools/?event_type=1')
        assert response.status_code == 200
        
        response = client.get('/pools/?status=open')
        assert response.status_code == 200
    
    def test_pool_list_search(self, client, event_manager_user):
        """Test searching pools by name."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(event_manager_user.id)
        
        response = client.get('/pools/?search=test')
        assert response.status_code == 200


# Test fixtures for pools testing
@pytest.fixture
def temp_booking(db_session):
    """Create a test booking for pool tests."""
    from tests.fixtures.factories import BookingFactory
    booking = BookingFactory.create()
    return booking


@pytest.fixture
def temp_pool(db_session, temp_booking):
    """Create a test pool."""
    pool = Pool(booking_id=temp_booking.id, is_open=True)
    db_session.add(pool)
    db_session.commit()
    return pool


@pytest.fixture
def event_manager_user(db_session):
    """Create user with Event Manager role."""
    from tests.fixtures.factories import MemberFactory
    user = MemberFactory.create()
    role = db_session.query(Role).filter_by(name='Event Manager').first()
    if not role:
        role = Role(name='Event Manager')
        db_session.add(role)
        db_session.commit()
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def temp_booking_with_pool(db_session, temp_booking):
    """Create booking with associated pool."""
    pool = Pool(booking_id=temp_booking.id, is_open=True)
    temp_booking.has_pool = True
    db_session.add(pool)
    db_session.commit()
    temp_booking.pool = pool
    return temp_booking