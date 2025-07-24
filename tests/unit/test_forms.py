"""
Unit tests for WTForms form validation.
"""
import pytest
from app.forms import (
    LoginForm, RequestResetForm, ResetPasswordForm, 
    PasswordChangeForm, EditProfileForm, MemberForm, EditMemberForm
)
from app.models import Member


@pytest.mark.unit
class TestLoginForm:
    """Test cases for LoginForm."""
    
    def test_valid_login_form(self, app):
        """Test valid login form data."""
        with app.app_context():
            form = LoginForm(data={
                'username': 'testuser',
                'password': 'testpassword123',
                'remember_me': True
            })
            
            assert form.validate() is True
            assert form.username.data == 'testuser'
            assert form.password.data == 'testpassword123'
            assert form.remember_me.data is True
    
    def test_empty_login_form(self, app):
        """Test login form with empty data."""
        with app.app_context():
            form = LoginForm(data={
                'username': '',
                'password': ''
            })
            
            assert form.validate() is False
            assert 'This field is required.' in form.username.errors
            assert 'This field is required.' in form.password.errors


@pytest.mark.unit  
class TestRequestResetForm:
    """Test cases for RequestResetForm."""
    
    def test_valid_reset_request(self, app):
        """Test valid password reset request."""
        with app.app_context():
            form = RequestResetForm(data={
                'email': 'test@example.com'
            })
            
            assert form.validate() is True
            assert form.email.data == 'test@example.com'
    
    def test_invalid_email_format(self, app):
        """Test invalid email format."""
        with app.app_context():
            form = RequestResetForm(data={
                'email': 'invalid-email'
            })
            
            assert form.validate() is False
            assert 'Invalid email address.' in form.email.errors


@pytest.mark.unit
class TestResetPasswordForm:
    """Test cases for ResetPasswordForm."""
    
    def test_valid_password_reset(self, app):
        """Test valid password reset."""
        with app.app_context():
            form = ResetPasswordForm(data={
                'password': 'NewPassword123!',
                'confirm_password': 'NewPassword123!'
            })
            
            assert form.validate() is True
            assert form.password.data == 'NewPassword123!'
    
    def test_password_mismatch(self, app):
        """Test password confirmation mismatch."""
        with app.app_context():
            form = ResetPasswordForm(data={
                'password': 'password123',
                'confirm_password': 'differentpassword'
            })
            
            assert form.validate() is False
            assert 'Field must be equal to password.' in form.confirm_password.errors
    
    def test_short_password(self, app):
        """Test password too short."""
        with app.app_context():
            form = ResetPasswordForm(data={
                'password': '123',
                'confirm_password': '123'
            })
            
            assert form.validate() is False
            assert 'Password must be at least 8 characters long' in form.password.errors


@pytest.mark.unit
class TestEditProfileForm:
    """Test cases for EditProfileForm."""
    
    def test_valid_profile_edit(self, app, db_session):
        """Test valid profile edit."""
        with app.app_context():
            form = EditProfileForm(
                original_email='test@example.com',
                data={
                    'firstname': 'John',
                    'lastname': 'Doe',
                    'email': 'john.doe@example.com', 
                    'phone': '123-456-7890',
                    'gender': 'Male',
                    'share_email': True,
                    'share_phone': False
                }
            )
            
            is_valid = form.validate()
            if not is_valid:
                print("Form validation errors:", form.errors)
            assert is_valid is True
            assert form.firstname.data == 'John'
            assert form.lastname.data == 'Doe'
            assert form.email.data == 'john.doe@example.com'
            assert form.phone.data == '123-456-7890'
            assert form.share_email.data is True
            assert form.share_phone.data is False
    
    def test_duplicate_email_validation(self, app, db_session):
        """Test duplicate email validation."""
        with app.app_context():
            # Create existing member
            existing_member = Member(
                username='existing',
                firstname='Existing',
                lastname='User',
                email='existing@example.com'
            )
            db_session.add(existing_member)
            db_session.commit()
            
            # Try to use existing email in form
            form = EditProfileForm(
                original_email='test@example.com',
                data={
                    'firstname': 'John',
                    'lastname': 'Doe', 
                    'email': 'existing@example.com',
                    'phone': '123-456-7890'
                }
            )
            
            assert form.validate() is False
            assert 'Please use a different email address.' in form.email.errors


@pytest.mark.unit
class TestMemberForm:
    """Test cases for MemberForm."""
    
    def test_valid_member_form(self, app, db_session):
        """Test valid member application form."""
        with app.app_context():
            form = MemberForm(data={
                'username': 'newmember',
                'firstname': 'New',
                'lastname': 'Member',
                'email': 'new@example.com',
                'phone': '123-456-7890',
                'password': 'NewPassword123!',
                'password2': 'NewPassword123!',
                'share_email': True,
                'share_phone': False
            })
            
            assert form.validate() is True
            assert form.username.data == 'newmember'
            assert form.firstname.data == 'New'
            assert form.lastname.data == 'Member'
            assert form.email.data == 'new@example.com'
    
    def test_duplicate_username_validation(self, app, db_session):
        """Test duplicate username validation."""
        with app.app_context():
            # Create existing member
            existing_member = Member(
                username='existing',
                firstname='Existing',
                lastname='User',
                email='existing@example.com'
            )
            db_session.add(existing_member)
            db_session.commit()
            
            # Try to use existing username in form
            form = MemberForm(data={
                'username': 'existing',
                'firstname': 'New',
                'lastname': 'Member',
                'email': 'new@example.com',
                'phone': '123-456-7890',
                'password': 'NewPassword123!',
                'password2': 'NewPassword123!'
            })
            
            assert form.validate() is False
            assert 'That username is not available. Please use a different username.' in form.username.errors