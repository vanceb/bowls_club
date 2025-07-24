"""
Integration tests for member admin routes.
"""
import pytest
import json
from flask import url_for
from app.models import Member, Role


@pytest.mark.integration
@pytest.mark.admin
class TestAdminRoutes:
    """Test cases for admin routes in members blueprint."""
    
    def test_manage_members_requires_role(self, authenticated_client):
        """Test manage members requires User Manager role."""
        response = authenticated_client.get('/members/admin/manage_members')
        
        assert response.status_code == 302  # Redirect due to insufficient permissions
    
    def test_manage_members_page_loads(self, client, user_manager_member):
        """Test manage members page loads for User Manager."""
        # Authenticate as user manager
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_manager_member.id)
            sess['_fresh'] = True
        
        response = client.get('/members/admin/manage_members')
        
        assert response.status_code == 200
        assert b'Manage Members' in response.data
    
    def test_edit_member_requires_role(self, authenticated_client, test_member):
        """Test edit member requires User Manager role."""
        response = authenticated_client.get(f'/members/admin/edit_member/{test_member.id}')
        
        assert response.status_code == 302  # Redirect due to insufficient permissions
    
    def test_edit_member_page_loads(self, client, user_manager_member, test_member):
        """Test edit member page loads for User Manager."""
        # Authenticate as user manager
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_manager_member.id)
            sess['_fresh'] = True
        
        response = client.get(f'/members/admin/edit_member/{test_member.id}')
        
        assert response.status_code == 200
        assert b'firstname' in response.data
        assert b'lastname' in response.data
        assert test_member.firstname.encode() in response.data
    
    def test_edit_member_nonexistent(self, client, user_manager_member):
        """Test edit nonexistent member returns 404."""
        # Authenticate as user manager
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_manager_member.id)
            sess['_fresh'] = True
        
        response = client.get('/members/admin/edit_member/99999')
        
        assert response.status_code == 302  # Redirect with error
    
    def test_reset_member_password_requires_role(self, authenticated_client, test_member):
        """Test reset member password requires User Manager role."""
        response = authenticated_client.get(f'/members/admin/reset_member_password/{test_member.id}')
        
        assert response.status_code == 302  # Redirect due to insufficient permissions
    
    def test_import_users_requires_admin(self, authenticated_client):
        """Test import users requires admin privileges."""
        response = authenticated_client.get('/members/admin/import_users')
        
        assert response.status_code == 302  # Redirect due to insufficient permissions
    
    def test_import_users_page_loads(self, admin_client):
        """Test import users page loads for admin."""
        response = admin_client.get('/members/admin/import_users')
        
        assert response.status_code == 200
        assert b'csv_data' in response.data
    
    def test_manage_roles_requires_role(self, authenticated_client):
        """Test manage roles requires User Manager role."""
        response = authenticated_client.get('/members/admin/manage_roles')
        
        assert response.status_code == 302  # Redirect due to insufficient permissions
    
    def test_manage_roles_page_loads(self, client, user_manager_member, core_roles):
        """Test manage roles page loads for User Manager."""
        # Authenticate as user manager
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_manager_member.id)
            sess['_fresh'] = True
        
        response = client.get('/members/admin/manage_roles')
        
        assert response.status_code == 200
        assert b'Manage Roles' in response.data
        assert b'User Manager' in response.data  # Should show core roles
    
    def test_create_role(self, client, user_manager_member, db_session):
        """Test creating a new role."""
        # Authenticate as user manager
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_manager_member.id)
            sess['_fresh'] = True
        
        response = client.post('/members/admin/manage_roles', data={
            'action': 'create_role',
            'role_name': 'Test Role'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Test Role' in response.data
        
        # Verify role was created in database
        role = db_session.query(Role).filter_by(name='Test Role').first()
        assert role is not None
    
    def test_create_duplicate_role(self, client, user_manager_member, core_roles):
        """Test creating duplicate role fails."""
        # Authenticate as user manager
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_manager_member.id)
            sess['_fresh'] = True
        
        response = client.post('/members/admin/manage_roles', data={
            'action': 'create_role',
            'role_name': 'User Manager'  # Already exists
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'already exists' in response.data
    
    def test_rename_role(self, client, user_manager_member, db_session):
        """Test renaming a role."""
        # Create test role
        test_role = Role(name='Original Role')
        db_session.add(test_role)
        db_session.commit()
        
        # Authenticate as user manager
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_manager_member.id)
            sess['_fresh'] = True
        
        response = client.post('/members/admin/manage_roles', data={
            'action': 'rename',
            'role_id': test_role.id,
            'role_name': 'Renamed Role'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'renamed' in response.data
        
        # Verify role was renamed in database
        db_session.refresh(test_role)
        assert test_role.name == 'Renamed Role'
    
    def test_rename_core_role_fails(self, client, user_manager_member, core_roles):
        """Test renaming core role fails."""
        user_manager_role = next(role for role in core_roles if role.name == 'User Manager')
        
        # Authenticate as user manager
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_manager_member.id)
            sess['_fresh'] = True
        
        response = client.post('/members/admin/manage_roles', data={
            'action': 'rename',
            'role_id': user_manager_role.id,
            'role_name': 'New Name'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Cannot rename core role' in response.data
    
    def test_delete_role(self, client, user_manager_member, db_session):
        """Test deleting a role."""
        # Create test role
        test_role = Role(name='Role to Delete')
        db_session.add(test_role)
        db_session.commit()
        role_id = test_role.id
        
        # Authenticate as user manager
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_manager_member.id)
            sess['_fresh'] = True
        
        response = client.post('/members/admin/manage_roles', data={
            'action': 'delete',
            'role_id': role_id
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'deleted successfully' in response.data
        
        # Verify role was deleted from database
        deleted_role = db_session.query(Role).filter_by(id=role_id).first()
        assert deleted_role is None
    
    def test_delete_core_role_fails(self, client, user_manager_member, core_roles):
        """Test deleting core role fails."""
        content_manager_role = next(role for role in core_roles if role.name == 'Content Manager')
        
        # Authenticate as user manager  
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_manager_member.id)
            sess['_fresh'] = True
        
        response = client.post('/members/admin/manage_roles', data={
            'action': 'delete',
            'role_id': content_manager_role.id
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Cannot delete core role' in response.data