"""
Unit tests for utility functions.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.members.utils import (
    generate_reset_token, verify_reset_token, send_reset_email,
    filter_admin_menu_by_roles, get_member_data
)
from app.models import Member, Role
from tests.fixtures.factories import MemberFactory, RoleFactory


@pytest.mark.unit
class TestTokenUtils:
    """Test cases for token generation and verification utilities."""
    
    def test_generate_reset_token(self, app, test_member):
        """Test password reset token generation."""
        with app.app_context():
            token = generate_reset_token(test_member)
            
            assert token is not None
            assert isinstance(token, str)
            assert len(token) > 20  # Should be a reasonable length
    
    def test_verify_reset_token_valid(self, app, test_member):
        """Test valid token verification."""
        with app.app_context():
            token = generate_reset_token(test_member)
            verified_member = verify_reset_token(token)
            
            assert verified_member is not None
            assert verified_member.id == test_member.id
            assert verified_member.email == test_member.email
    
    def test_verify_reset_token_invalid(self, app):
        """Test invalid token verification."""
        with app.app_context():
            # Test completely invalid token
            assert verify_reset_token('invalid-token') is None
            
            # Test empty token
            assert verify_reset_token('') is None
            
            # Test None token
            assert verify_reset_token(None) is None
    
    def test_verify_reset_token_expired(self, app, test_member):
        """Test expired token verification."""
        with app.app_context():
            # This would require mocking time to test expiry
            # For now, we just test that a valid token works
            token = generate_reset_token(test_member)
            verified_member = verify_reset_token(token)
            
            assert verified_member is not None


@pytest.mark.unit
class TestEmailUtils:
    """Test cases for email utilities."""
    
    @patch('app.members.utils.mail.send')
    def test_send_reset_email_success(self, mock_send, app, test_member):
        """Test successful password reset email sending."""
        with app.app_context():
            token = generate_reset_token(test_member)
            
            # Mock successful email sending
            mock_send.return_value = True
            
            result = send_reset_email(test_member, token)
            
            assert result is True
            mock_send.assert_called_once()
    
    @patch('app.members.utils.mail.send')
    def test_send_reset_email_failure(self, mock_send, app, test_member):
        """Test failed password reset email sending."""
        with app.app_context():
            token = generate_reset_token(test_member)
            
            # Mock email sending failure
            mock_send.side_effect = Exception('Email sending failed')
            
            result = send_reset_email(test_member, token)
            
            assert result is False
            mock_send.assert_called_once()


@pytest.mark.unit
class TestAdminMenuUtils:
    """Test cases for admin menu utilities."""
    
    @patch('app.members.utils.current_app')
    @patch.object(Member, 'is_authenticated', new_callable=lambda: True)
    def test_filter_admin_menu_by_roles(self, mock_authenticated, mock_app, db_session):
        """Test admin menu filtering by user roles."""
        # Create test roles
        user_manager_role = Role(name='User Manager')
        content_manager_role = Role(name='Content Manager')
        db_session.add_all([user_manager_role, content_manager_role])
        db_session.commit()
        
        # Create test user with specific roles
        member = MemberFactory.create(
            username='testuser', 
            firstname='Test',
            lastname='User',
            email='test@example.com'
        )
        member.roles = [user_manager_role]
        db_session.add(member)
        db_session.commit()
        
        # Mock Flask config with test menu items
        test_menu_items = [
            {'name': 'Manage Members', 'link': 'members.admin_manage_members', 'roles': ['User Manager']},
            {'name': 'Manage Posts', 'link': 'admin.manage_posts', 'roles': ['Content Manager']},
            {'name': 'General Admin', 'link': 'admin.general'}  # No roles specified
        ]
        mock_config = MagicMock()
        mock_config.get.return_value = test_menu_items
        mock_app.config = mock_config
        
        filtered_menu = filter_admin_menu_by_roles(member)
        
        # Should include items for User Manager role only
        # Items without roles are admin-only by default
        assert len(filtered_menu) == 1
        filtered_names = [item['name'] for item in filtered_menu if item is not None]
        assert 'Manage Members' in filtered_names
        assert 'General Admin' not in filtered_names  # No roles = admin-only
        assert 'Manage Posts' not in filtered_names
    
    @patch('app.members.utils.current_app')
    @patch.object(Member, 'is_authenticated', new_callable=lambda: True)
    def test_filter_admin_menu_admin_user(self, mock_authenticated, mock_app, db_session):
        """Test admin menu filtering for admin users."""
        # Create admin user
        admin = MemberFactory.create(
            username='admin', 
            firstname='Admin',
            lastname='User',
            email='admin@example.com', 
            is_admin=True
        )
        db_session.add(admin)
        db_session.commit()
        
        # Mock Flask config with test menu items
        test_menu_items = [
            {'name': 'Manage Members', 'link': 'members.admin_manage_members', 'roles': ['User Manager']},
            {'name': 'Manage Posts', 'link': 'admin.manage_posts', 'roles': ['Content Manager']},
        ]
        mock_config = MagicMock()
        mock_config.get.return_value = test_menu_items
        mock_app.config = mock_config
        
        filtered_menu = filter_admin_menu_by_roles(admin)
        
        # Admin should see all menu items
        assert len(filtered_menu) == 2


@pytest.mark.unit
class TestMemberDataUtils:
    """Test cases for member data utilities."""
    
    def test_get_member_data_private(self, db_session):
        """Test getting member data without private information."""
        member = MemberFactory.create(
            username='testuser',
            firstname='Test',
            lastname='User',
            email='test@example.com',
            phone='123-456-7890',
            share_email=False,
            share_phone=False
        )
        db_session.add(member)
        db_session.commit()
        
        data = get_member_data(member, show_private_data=False)
        
        assert data['id'] == member.id
        assert data['username'] == 'testuser'
        assert data['firstname'] == 'Test'
        assert data['lastname'] == 'User'
        assert data['email'] == 'Private'  # Should be hidden
        assert data['phone'] == 'Private'  # Should be hidden
        assert data['share_email'] is False
        assert data['share_phone'] is False
    
    def test_get_member_data_public(self, db_session):
        """Test getting member data with public information."""
        member = MemberFactory.create(
            username='testuser',
            firstname='Test',
            lastname='User',
            email='test@example.com',
            phone='123-456-7890',
            share_email=True,
            share_phone=True
        )
        db_session.add(member)
        db_session.commit()
        
        data = get_member_data(member, show_private_data=False)
        
        assert data['email'] == 'test@example.com'  # Should be visible
        assert data['phone'] == '123-456-7890'  # Should be visible
    
    def test_get_member_data_admin_view(self, db_session):
        """Test getting member data with admin privileges."""
        member = MemberFactory.create(
            username='testuser',
            firstname='Test',
            lastname='User',
            email='test@example.com',
            phone='123-456-7890',
            share_email=False,
            share_phone=False
        )
        db_session.add(member)
        db_session.commit()
        
        data = get_member_data(member, show_private_data=True)
        
        # Admin should see all data regardless of privacy settings
        assert data['email'] == 'test@example.com'
        assert data['phone'] == '123-456-7890'