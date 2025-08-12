"""
Integration tests for member API routes.
"""
import pytest
import json
from app.models import Member, Role
from tests.fixtures.factories import MemberFactory


@pytest.mark.integration
@pytest.mark.api
class TestMemberAPIRoutes:
    """Test cases for member API routes."""
    
    def test_search_members_requires_login(self, client):
        """Test member search API requires authentication."""
        response = client.get('/members/api/v1/search')
        
        assert response.status_code == 302  # Redirect to login
    
    def test_search_members_empty_query(self, authenticated_client, db_session):
        """Test member search with empty query returns all active members."""
        # Create test members
        member1 = MemberFactory.create(username='user1', firstname='John', lastname='Doe', 
                        email='john@test.com', status='Full')
        member2 = MemberFactory.create(username='user2', firstname='Jane', lastname='Smith', 
                        email='jane@test.com', status='Full')  
        member3 = MemberFactory.create(username='user3', firstname='Bob', lastname='Wilson',
                        email='bob@test.com', status='Pending')  # Should be excluded
        
        db_session.add_all([member1, member2, member3])
        db_session.commit()
        
        response = authenticated_client.get('/members/api/v1/search')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['count'] >= 2  # At least our test members + fixture member
        
        # Check that only active members are returned
        usernames = [member['username'] for member in data['members']]
        assert 'user1' in usernames
        assert 'user2' in usernames
        assert 'user3' not in usernames  # Pending member excluded
    
    def test_search_members_with_query(self, authenticated_client, db_session):
        """Test member search with search query."""
        # Create test members
        member1 = MemberFactory.create(username='johndoe', firstname='John', lastname='Doe',
                        email='john@test.com', status='Full')
        member2 = MemberFactory.create(username='janedoe', firstname='Jane', lastname='Doe',
                        email='jane@test.com', status='Full')
        member3 = MemberFactory.create(username='bobsmith', firstname='Bob', lastname='Smith',
                        email='bob@test.com', status='Full')
        
        db_session.add_all([member1, member2, member3])
        db_session.commit()
        
        # Search for "Doe"
        response = authenticated_client.get('/members/api/v1/search?q=Doe')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['count'] >= 2
        
        # Should return both Doe members
        lastnames = [member['lastname'] for member in data['members']]
        assert 'Doe' in lastnames
    
    def test_search_members_admin_context(self, admin_client, db_session):
        """Test member search with admin context includes pending members."""
        # Create test members
        pending_member = MemberFactory.create(username='pending', firstname='Pending', lastname='User',
                              email='pending@test.com', status='Pending')
        active_member = MemberFactory.create(username='active', firstname='Active', lastname='User',
                             email='active@test.com', status='Full')
        
        db_session.add_all([pending_member, active_member])
        db_session.commit()
        
        # Search with manage_members context (admin view)
        response = admin_client.get('/members/api/v1/search?route=manage_members')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Should include pending members for admin
        usernames = [member['username'] for member in data['members']]
        assert 'pending' in usernames
        assert 'active' in usernames
    
    def test_search_members_privacy_filtering(self, authenticated_client, db_session):
        """Test member search respects privacy settings."""
        # Create member with private contact info
        private_member = MemberFactory.create(
            username='private', firstname='Private', lastname='User',
            email='private@test.com', phone='123-456-7890',
            status='Full', share_email=False, share_phone=False
        )
        
        db_session.add(private_member)
        db_session.commit()
        
        response = authenticated_client.get('/members/api/v1/search?q=Private')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Find our private member in results
        private_result = next((m for m in data['members'] if m['username'] == 'private'), None)
        assert private_result is not None
        
        # Email and phone should be marked as private
        assert private_result['email'] == 'Private'
        assert private_result['phone'] == 'Private'
    
    def test_search_members_admin_sees_private_data(self, admin_client, db_session):
        """Test admin user can see all member data regardless of privacy settings."""
        # Create member with private contact info
        private_member = MemberFactory.create(
            username='private', firstname='Private', lastname='User',
            email='private@test.com', phone='123-456-7890',
            status='Full', share_email=False, share_phone=False
        )
        
        db_session.add(private_member)
        db_session.commit()
        
        response = admin_client.get('/members/api/v1/search?q=Private&route=manage_members')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Find our private member in results
        private_result = next((m for m in data['members'] if m['username'] == 'private'), None)
        assert private_result is not None
        
        # Admin should see actual data, not "Private"
        assert private_result['email'] == 'private@test.com'
        assert private_result['phone'] == '123-456-7890'
    
    def test_users_with_roles_requires_admin(self, authenticated_client):
        """Test users with roles API requires admin privileges."""
        response = authenticated_client.get('/members/api/v1/users_with_roles')
        
        assert response.status_code == 302  # Redirect due to insufficient permissions
    
    def test_users_with_roles_admin_access(self, admin_client, db_session, core_roles):
        """Test users with roles API works for admin."""
        # Create user with role
        user_with_role = MemberFactory.create(username='roleuser', firstname='Role', lastname='User',
                               email='role@test.com', status='Full')
        user_with_role.roles = [core_roles[0]]  # Assign first core role
        db_session.add(user_with_role)
        db_session.commit()
        
        response = admin_client.get('/members/api/v1/users_with_roles')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['count'] >= 1
        assert len(data['users']) >= 1
        
        # Find our test user
        test_user = next((u for u in data['users'] if u['username'] == 'roleuser'), None)
        assert test_user is not None
        assert len(test_user['roles']) >= 1
        assert test_user['roles'][0]['name'] == core_roles[0].name
    
    def test_add_user_to_role_requires_permission(self, authenticated_client):
        """Test add user to role requires User Manager role."""
        response = authenticated_client.post('/members/admin/add_user_to_role',
                                           json={'user_id': 1, 'role_id': 1})
        
        assert response.status_code == 302  # Redirect due to insufficient permissions
    
    def test_add_user_to_role_success(self, client, user_manager_member, test_member, core_roles):
        """Test successfully adding user to role."""
        # Authenticate as user manager
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_manager_member.id)
            sess['_fresh'] = True
        
        role = core_roles[0]
        
        response = client.post('/members/admin/add_user_to_role',
                             json={'user_id': test_member.id, 'role_id': role.id})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert role.name in data['message']
    
    def test_add_user_to_role_already_has_role(self, client, user_manager_member, core_roles, db_session):
        """Test adding user to role they already have."""
        # Create user with role
        user_with_role = MemberFactory.create(username='roleuser', email='role@test.com', status='Full')
        role = core_roles[0]
        user_with_role.roles = [role]
        db_session.add(user_with_role)
        db_session.commit()
        
        # Authenticate as user manager
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_manager_member.id)
            sess['_fresh'] = True
        
        response = client.post('/members/admin/add_user_to_role',
                             json={'user_id': user_with_role.id, 'role_id': role.id})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
        assert 'already has' in data['message']
    
    def test_remove_user_from_role_success(self, client, user_manager_member, core_roles, db_session):
        """Test successfully removing user from role."""
        # Create user with role
        user_with_role = MemberFactory.create(username='roleuser', email='role@test.com', status='Full')
        role = core_roles[0]
        user_with_role.roles = [role]
        db_session.add(user_with_role)
        db_session.commit()
        
        # Authenticate as user manager
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_manager_member.id)
            sess['_fresh'] = True
        
        response = client.post('/members/admin/remove_user_from_role',
                             json={'user_id': user_with_role.id, 'role_id': role.id})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'Removed' in data['message']
    
    def test_api_error_handling(self, authenticated_client):
        """Test API error handling for invalid requests."""
        # Test with invalid member ID
        response = authenticated_client.get('/members/api/v1/search?q=nonexistent')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['count'] == 0
        assert data['members'] == []