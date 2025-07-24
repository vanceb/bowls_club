"""
Integration tests for member authentication routes.
"""
import pytest
from flask import url_for
from app.models import Member


@pytest.mark.integration
@pytest.mark.auth
class TestAuthRoutes:
    """Test cases for authentication routes in members blueprint."""
    
    def test_login_page_loads(self, client):
        """Test login page loads correctly."""
        response = client.get('/members/auth/login')
        
        assert response.status_code == 200
        assert b'Sign In' in response.data
        assert b'username' in response.data
        assert b'password' in response.data
    
    def test_login_success(self, client, test_member):
        """Test successful login."""
        response = client.post('/members/auth/login', data={
            'username': 'testuser',
            'password': 'testpassword123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Welcome back' in response.data
    
    def test_login_invalid_credentials(self, client, test_member):
        """Test login with invalid credentials."""
        response = client.post('/members/auth/login', data={
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        
        assert response.status_code == 200
        assert b'Invalid username or password' in response.data
    
    def test_login_nonexistent_user(self, client, db_session):
        """Test login with nonexistent user."""
        response = client.post('/members/auth/login', data={
            'username': 'nonexistent',
            'password': 'anypassword'
        })
        
        assert response.status_code == 200
        assert b'Invalid username or password' in response.data
    
    def test_login_locked_account(self, client, db_session):
        """Test login with locked account."""
        # Create locked member
        locked_member = Member(
            username='lockeduser',
            firstname='Locked',
            lastname='User',
            email='locked@example.com',
            lockout=True
        )
        locked_member.set_password('password123')
        db_session.add(locked_member)
        db_session.commit()
        
        response = client.post('/members/auth/login', data={
            'username': 'lockeduser',
            'password': 'password123'
        })
        
        assert response.status_code == 200
        assert b'Your account has been locked' in response.data
    
    def test_logout(self, authenticated_client):
        """Test logout functionality."""
        response = authenticated_client.get('/members/auth/logout', follow_redirects=True)
        
        assert response.status_code == 200
        assert b'You have been logged out' in response.data
    
    def test_password_reset_request_page(self, client):
        """Test password reset request page loads."""
        response = client.get('/members/auth/reset_password')
        
        assert response.status_code == 200
        assert b'email' in response.data
    
    def test_password_reset_request_valid_email(self, client, test_member):
        """Test password reset request with valid email."""
        response = client.post('/members/auth/reset_password', data={
            'email': 'test@example.com'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'If that email address is in our system' in response.data
    
    def test_password_reset_request_invalid_email(self, client, db_session):
        """Test password reset request with nonexistent email."""
        response = client.post('/members/auth/reset_password', data={
            'email': 'nonexistent@example.com'
        }, follow_redirects=True)
        
        # Should show same message for security (email enumeration protection)
        assert response.status_code == 200
        assert b'If that email address is in our system' in response.data
    
    def test_password_change_requires_login(self, client):
        """Test password change requires authentication."""
        response = client.get('/members/auth/change_password')
        
        assert response.status_code == 302  # Redirect to login
    
    def test_password_change_page_loads(self, authenticated_client):
        """Test password change page loads for authenticated user."""
        response = authenticated_client.get('/members/auth/change_password')
        
        assert response.status_code == 200
        assert b'current_password' in response.data
        assert b'password' in response.data
    
    def test_profile_requires_login(self, client):
        """Test profile page requires authentication."""
        response = client.get('/members/auth/profile')
        
        assert response.status_code == 302  # Redirect to login
    
    def test_profile_page_loads(self, authenticated_client):
        """Test profile page loads for authenticated user."""
        response = authenticated_client.get('/members/auth/profile')
        
        assert response.status_code == 200
        assert b'firstname' in response.data
        assert b'lastname' in response.data
        assert b'email' in response.data