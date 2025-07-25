"""
Unit tests for content blueprint forms.
"""
import pytest
from datetime import date, timedelta


class TestWritePostForm:
    """Test cases for WritePostForm."""
    
    def test_write_post_form_imports(self):
        """Test WritePostForm can be imported."""
        from app.content.forms import WritePostForm
        assert WritePostForm is not None
    
    def test_write_post_form_has_required_fields(self, app):
        """Test WritePostForm has all required fields."""
        with app.app_context():
            from app.content.forms import WritePostForm
            
            form = WritePostForm()
            
            # Check required fields exist
            assert hasattr(form, 'title')
            assert hasattr(form, 'summary') 
            assert hasattr(form, 'content')
            assert hasattr(form, 'publish_on')
            assert hasattr(form, 'expires_on')
            assert hasattr(form, 'pin_until')
            assert hasattr(form, 'tags')
            assert hasattr(form, 'submit')
    
    def test_write_post_form_validation(self, app):
        """Test WritePostForm validation."""
        with app.app_context():
            from app.content.forms import WritePostForm
            
            # Test empty form fails validation
            form = WritePostForm(data={}, csrf_token=False)
            assert not form.validate()
            
            # Test form with required fields
            valid_data = {
                'title': 'Test Post',
                'summary': 'Test Summary',
                'content': 'Test Content',
                'publish_on': date.today(),
                'expires_on': date.today() + timedelta(days=30)
            }
            
            form = WritePostForm(data=valid_data, csrf_token=False)
            # Check that required fields are present and have data
            assert form.title.data == 'Test Post'
            assert form.summary.data == 'Test Summary'
            assert form.content.data == 'Test Content'


class TestPolicyPageForm:
    """Test cases for PolicyPageForm."""
    
    def test_policy_page_form_imports(self):
        """Test PolicyPageForm can be imported."""
        from app.content.forms import PolicyPageForm
        assert PolicyPageForm is not None
    
    def test_policy_page_form_has_required_fields(self, app):
        """Test PolicyPageForm has all required fields."""
        with app.app_context():
            from app.content.forms import PolicyPageForm
            
            form = PolicyPageForm()
            
            # Check required fields exist
            assert hasattr(form, 'title')
            assert hasattr(form, 'slug')
            assert hasattr(form, 'description')
            assert hasattr(form, 'content')
            assert hasattr(form, 'is_active')
            assert hasattr(form, 'show_in_footer')
            assert hasattr(form, 'sort_order')
            assert hasattr(form, 'submit')
    
    def test_policy_page_form_validation(self, app):
        """Test PolicyPageForm validation."""
        with app.app_context():
            from app.content.forms import PolicyPageForm
            
            # Test empty form fails validation
            form = PolicyPageForm(data={}, csrf_token=False)
            assert not form.validate()
            
            # Test form with required fields
            valid_data = {
                'title': 'Test Policy',
                'slug': 'test-policy', 
                'description': 'Test Description',
                'content': 'Test Content',
                'is_active': True,
                'show_in_footer': False,
                'sort_order': 1
            }
            
            form = PolicyPageForm(data=valid_data, csrf_token=False)
            # Check that required fields are present and have data
            assert form.title.data == 'Test Policy'
            assert form.slug.data == 'test-policy'
            assert form.description.data == 'Test Description'
            assert form.content.data == 'Test Content'