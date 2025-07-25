"""
Integration tests for content blueprint routes.
Tests for all migrated content management functionality.
"""
import pytest
from app.models import Member, Role, Post, PolicyPage
from datetime import date, timedelta


@pytest.mark.integration
class TestContentPublicRoutes:
    """Test cases for public content routes."""
    
    def test_view_post_requires_login(self, client, db_session):
        """Test viewing a post requires authentication."""
        # Create a test post
        post = Post(
            title="Test Post",
            summary="Test Summary", 
            publish_on=date.today(),
            expires_on=date.today() + timedelta(days=30),
            markdown_filename="test.md",
            html_filename="test.html",
            author_id=1
        )
        db_session.add(post)
        db_session.commit()
        
        response = client.get(f'/content/post/{post.id}')
        assert response.status_code == 302  # Redirect to login
    
    def test_view_policy_requires_login(self, client, db_session):
        """Test viewing a policy page requires authentication."""
        # Create a test policy page with all required fields
        policy = PolicyPage(
            title="Test Policy",
            slug="test-policy",
            description="Test Description",
            is_active=True,
            show_in_footer=False,
            sort_order=1,
            markdown_filename="test.md",
            html_filename="test.html",
            author_id=1
        )
        db_session.add(policy)
        db_session.commit()
        
        response = client.get('/content/policy/test-policy')
        assert response.status_code == 302  # Redirect to login


@pytest.mark.integration
class TestContentAdminRoutes:
    """Test cases for content admin routes."""
    
    def test_admin_write_post_requires_login(self, client):
        """Test write post page requires authentication."""
        response = client.get('/content/admin/write_post')
        assert response.status_code == 302  # Redirect to login
    
    def test_admin_write_post_requires_content_manager_role(self, authenticated_client, test_member):
        """Test write post requires Content Manager role."""
        response = authenticated_client.get('/content/admin/write_post')
        # Should return 403 since user doesn't have Content Manager role
        assert response.status_code == 403
    
    def test_admin_write_post_loads_for_content_manager(self, client, db_session):
        """Test write post page loads for Content Manager."""
        # Create Content Manager role
        role = Role(name='Content Manager')
        db_session.add(role)
        
        # Create user with Content Manager role
        user = Member(
            username='content_manager',
            firstname='Content',
            lastname='Manager',
            email='content@test.com',
            status='Full'
        )
        user.set_password('testpass123!')
        user.roles.append(role)
        db_session.add(user)
        db_session.commit()
        
        # Login as content manager
        login_response = client.post('/members/auth/login', data={
            'username': 'content_manager',
            'password': 'testpass123!'
        })
        
        # Test write post page loads
        response = client.get('/content/admin/write_post')
        assert response.status_code == 200
        assert b'Write or Edit Post' in response.data
    
    def test_admin_manage_posts_requires_content_manager_role(self, authenticated_client):
        """Test manage posts requires Content Manager role."""
        response = authenticated_client.get('/content/admin/manage_posts')
        assert response.status_code == 403
    
    def test_admin_manage_policy_pages_requires_content_manager_role(self, authenticated_client):
        """Test manage policy pages requires Content Manager role."""
        response = authenticated_client.get('/content/admin/manage_policy_pages')
        assert response.status_code == 403
    
    def test_admin_create_policy_page_requires_content_manager_role(self, authenticated_client):
        """Test create policy page requires Content Manager role."""
        response = authenticated_client.get('/content/admin/create_policy_page')
        assert response.status_code == 403


@pytest.mark.integration 
class TestContentBlueprintRegistration:
    """Test cases for content blueprint registration and URL routing."""
    
    def test_content_blueprint_routes_registered(self, app):
        """Test that all content blueprint routes are properly registered."""
        with app.app_context():
            # Check that content blueprint routes exist
            rules = [rule for rule in app.url_map.iter_rules() 
                    if rule.endpoint and rule.endpoint.startswith('content.')]
            
            # Should have 11 routes (9 admin + 2 public)
            assert len(rules) >= 11
            
            # Check specific routes exist
            endpoints = [rule.endpoint for rule in rules]
            expected_endpoints = [
                'content.admin_write_post',
                'content.admin_manage_posts', 
                'content.admin_edit_post',
                'content.admin_delete_post',
                'content.admin_manage_policy_pages',
                'content.admin_create_policy_page',
                'content.admin_edit_policy_page',
                'content.admin_delete_policy_page',
                'content.admin_recover_policy_page',
                'content.view_post',
                'content.view_policy'
            ]
            
            for endpoint in expected_endpoints:
                assert endpoint in endpoints, f"Missing endpoint: {endpoint}"
    
    def test_content_routes_have_correct_url_prefix(self, app):
        """Test that content routes have /content prefix."""
        with app.app_context():
            content_rules = [rule for rule in app.url_map.iter_rules() 
                           if rule.endpoint and rule.endpoint.startswith('content.')]
            
            for rule in content_rules:
                assert rule.rule.startswith('/content/'), f"Route {rule.rule} should start with /content/"


@pytest.mark.integration
class TestContentFormsAndUtils:
    """Test cases for content forms and utilities."""
    
    def test_write_post_form_imports_correctly(self):
        """Test that WritePostForm can be imported from content blueprint."""
        from app.content.forms import WritePostForm
        assert WritePostForm is not None
    
    def test_policy_page_form_imports_correctly(self):
        """Test that PolicyPageForm can be imported from content blueprint.""" 
        from app.content.forms import PolicyPageForm
        assert PolicyPageForm is not None
    
    def test_content_utils_import_correctly(self):
        """Test that content utilities can be imported."""
        from app.content.utils import (
            generate_secure_filename, 
            get_secure_post_path,
            sanitize_html_content
        )
        assert generate_secure_filename is not None
        assert get_secure_post_path is not None
        assert sanitize_html_content is not None


@pytest.mark.integration
class TestContentTemplateRendering:
    """Test cases for content template rendering."""
    
    def test_content_templates_exist(self):
        """Test that content templates exist in correct location."""
        import os
        template_dir = '/home/vance/code/bowls_club/app/content/templates'
        
        expected_templates = [
            'admin_write_post.html',
            'admin_manage_posts.html', 
            'admin_manage_policy_pages.html',
            'admin_policy_page_form.html',
            'view_post.html',
            'view_policy_page.html'
        ]
        
        for template in expected_templates:
            template_path = os.path.join(template_dir, template)
            assert os.path.exists(template_path), f"Template not found: {template}"


@pytest.mark.integration 
class TestContentNavigationMenus:
    """Test cases for content navigation menu integration."""
    
    def test_content_menu_items_use_correct_blueprint_prefix(self, app):
        """Test that menu configuration uses content blueprint prefix."""
        with app.app_context():
            admin_menu = app.config.get('ADMIN_MENU_ITEMS', [])
            
            # Find content-related menu items
            content_items = [item for item in admin_menu 
                           if item and isinstance(item, dict) and 
                           'link' in item and 'content.' in item['link']]
            
            # Should have content menu items
            assert len(content_items) > 0
            
            # Check specific menu items
            content_links = [item['link'] for item in content_items]
            expected_links = [
                'content.admin_write_post',
                'content.admin_manage_posts',
                'content.admin_manage_policy_pages'
            ]
            
            for link in expected_links:
                assert link in content_links, f"Missing menu link: {link}"


@pytest.mark.integration
class TestContentURLForGeneration:
    """Test cases for URL generation with content blueprint."""
    
    def test_url_for_content_routes_work(self, app):
        """Test that url_for works correctly for content routes."""
        with app.app_context():
            from flask import url_for
            
            # Test public routes
            post_url = url_for('content.view_post', post_id=1)
            assert post_url == '/content/post/1'
            
            policy_url = url_for('content.view_policy', slug='test-policy')
            assert policy_url == '/content/policy/test-policy'
            
            # Test admin routes  
            write_post_url = url_for('content.admin_write_post')
            assert write_post_url == '/content/admin/write_post'
            
            manage_posts_url = url_for('content.admin_manage_posts')
            assert manage_posts_url == '/content/admin/manage_posts'
            
            manage_policy_url = url_for('content.admin_manage_policy_pages')
            assert manage_policy_url == '/content/admin/manage_policy_pages'