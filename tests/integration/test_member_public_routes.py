"""
Integration tests for public member routes (directory, apply).
"""
import pytest
from app.models import Member


@pytest.mark.integration
class TestPublicMemberRoutes:
    """Test cases for public member routes."""
    
    def test_member_directory_requires_login(self, client):
        """Test member directory requires authentication."""
        response = client.get('/members/directory')
        
        assert response.status_code == 302  # Redirect to login
    
    def test_member_directory_loads(self, authenticated_client, db_session):
        """Test member directory page loads for authenticated user."""
        # Create some test members
        member1 = Member(username='john', firstname='John', lastname='Doe',
                        email='john@test.com', status='Full')
        member2 = Member(username='jane', firstname='Jane', lastname='Smith',
                        email='jane@test.com', status='Social')
        pending_member = Member(username='pending', firstname='Pending', lastname='User',
                              email='pending@test.com', status='Pending')  # Should not appear
        
        db_session.add_all([member1, member2, pending_member])
        db_session.commit()
        
        response = authenticated_client.get('/members/directory')
        
        assert response.status_code == 200
        assert b'Members' in response.data
        assert b'Search Members' in response.data
        
        # Check that active members appear but pending don't
        assert b'John' in response.data
        assert b'Jane' in response.data
        assert b'Pending' not in response.data
    
    def test_member_directory_privacy_respected(self, authenticated_client, db_session):
        """Test member directory respects privacy settings."""
        # Create member with private contact info
        private_member = Member(
            username='private', firstname='Private', lastname='User',
            email='private@test.com', phone='123-456-7890', 
            status='Full', share_email=False, share_phone=False
        )
        
        # Create member with public contact info
        public_member = Member(
            username='public', firstname='Public', lastname='User',
            email='public@test.com', phone='987-654-3210',
            status='Full', share_email=True, share_phone=True
        )
        
        db_session.add_all([private_member, public_member])
        db_session.commit()
        
        response = authenticated_client.get('/members/directory')
        
        assert response.status_code == 200
        
        # Public member info should be visible
        assert b'public@test.com' in response.data
        assert b'987-654-3210' in response.data
        
        # Private member info should show as "Private"
        assert b'private@test.com' not in response.data
        assert b'123-456-7890' not in response.data
        assert b'Private' in response.data
    
    def test_member_apply_page_loads(self, client):
        """Test member application page loads without authentication."""
        response = client.get('/members/apply')
        
        assert response.status_code == 200
        assert b'Apply to Join' in response.data
        assert b'username' in response.data
        assert b'firstname' in response.data
        assert b'lastname' in response.data
        assert b'email' in response.data
    
    def test_member_apply_success(self, client, db_session):
        """Test successful member application."""
        response = client.post('/members/apply', data={
            'username': 'newmember',
            'firstname': 'New',
            'lastname': 'Member',
            'email': 'new@example.com',
            'phone': '555-0123',
            'password': 'password123',
            'confirm_password': 'password123',
            'share_email': True,
            'share_phone': False
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Thank you for your application' in response.data
        
        # Verify member was created with Pending status
        new_member = db_session.query(Member).filter_by(username='newmember').first()
        assert new_member is not None
        assert new_member.status == 'Pending'
        assert new_member.firstname == 'New'
        assert new_member.lastname == 'Member'
        assert new_member.email == 'new@example.com'
        assert new_member.share_email is True
        assert new_member.share_phone is False
        assert new_member.check_password('password123')
    
    def test_member_apply_duplicate_username(self, client, test_member):
        """Test member application with duplicate username fails."""
        response = client.post('/members/apply', data={
            'username': 'testuser',  # Already exists
            'firstname': 'New',
            'lastname': 'Member',
            'email': 'new@example.com',
            'phone': '555-0123',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        
        assert response.status_code == 200
        assert b'Please use a different username' in response.data
    
    def test_member_apply_duplicate_email(self, client, test_member):
        """Test member application with duplicate email fails."""
        response = client.post('/members/apply', data={
            'username': 'newmember',
            'firstname': 'New',
            'lastname': 'Member',
            'email': 'test@example.com',  # Already exists
            'phone': '555-0123',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        
        assert response.status_code == 200
        assert b'Please use a different email' in response.data
    
    def test_member_apply_password_mismatch(self, client):
        """Test member application with password mismatch fails."""
        response = client.post('/members/apply', data={
            'username': 'newmember',
            'firstname': 'New',
            'lastname': 'Member',
            'email': 'new@example.com',
            'phone': '555-0123',
            'password': 'password123',
            'confirm_password': 'differentpassword'
        })
        
        assert response.status_code == 200
        assert b'Field must be equal to password' in response.data
    
    def test_member_apply_invalid_email(self, client):
        """Test member application with invalid email fails."""
        response = client.post('/members/apply', data={
            'username': 'newmember',
            'firstname': 'New',
            'lastname': 'Member',
            'email': 'invalid-email',
            'phone': '555-0123',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        
        assert response.status_code == 200
        assert b'Invalid email address' in response.data
    
    def test_member_apply_bootstrap_mode(self, client, db_session):
        """Test member application in bootstrap mode creates admin user."""
        # Ensure no members exist (bootstrap mode)
        db_session.query(Member).delete()
        db_session.commit()
        
        response = client.post('/members/apply', data={
            'username': 'admin',
            'firstname': 'Admin',
            'lastname': 'User',
            'email': 'admin@example.com',
            'phone': '555-0123',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Admin user' in response.data
        assert b'full access' in response.data
        
        # Verify admin was created
        admin_user = db_session.query(Member).filter_by(username='admin').first()
        assert admin_user is not None
        assert admin_user.is_admin is True
        assert admin_user.status == 'Full'  # Not Pending in bootstrap mode
    
    def test_member_apply_empty_form(self, client):
        """Test member application with empty form fails validation."""
        response = client.post('/members/apply', data={})
        
        assert response.status_code == 200
        assert b'This field is required' in response.data