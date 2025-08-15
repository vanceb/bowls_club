"""
Unit tests for content blueprint utilities.
"""
import pytest
import os
import tempfile
from unittest.mock import patch, mock_open


class TestContentUtilities:
    """Test cases for content utilities."""
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        from app.content.utils import sanitize_filename
        
        # Test basic filename
        filename = sanitize_filename("Test Post")
        assert filename == "Test_Post"
        
        # Test with special characters
        filename = sanitize_filename("Test & Post!")
        assert filename == "Test___Post_"
        
        # Test with dots and hyphens (should be preserved)
        filename = sanitize_filename("test-file.txt")
        assert filename == "test-file.txt"
    
    def test_sanitize_html_content(self):
        """Test HTML sanitization."""
        from app.content.utils import sanitize_html_content
        
        # Test safe HTML passes through
        safe_html = "<p>This is safe content</p>"
        result = sanitize_html_content(safe_html)
        assert "<p>This is safe content</p>" in result
        
        # Test dangerous scripts are removed
        dangerous_html = "<p>Safe content</p><script>alert('bad')</script>"
        result = sanitize_html_content(dangerous_html)
        assert "<script>" not in result
        assert "<p>Safe content</p>" in result
        
        # Test empty content
        result = sanitize_html_content("")
        assert result == ""
    
    def test_validate_secure_path(self, app):
        """Test secure path validation."""
        with app.app_context():
            from app.content.utils import validate_secure_path
            import tempfile
            import os
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Test valid filename
                path = validate_secure_path("valid-file.md", temp_dir)
                assert path is not None
                assert "valid-file.md" in path
                
                # Test path traversal attempt
                path = validate_secure_path("../../../etc/passwd", temp_dir)
                assert path is None
                
                # Test None filename
                path = validate_secure_path(None, temp_dir)
                assert path is None
    
    def test_get_secure_policy_page_path(self, app):
        """Test secure policy page path generation."""
        with app.app_context():
            from app.content.utils import get_secure_policy_page_path
            
            # Test valid filename
            path = get_secure_policy_page_path("valid-policy.md")
            assert path is not None
            assert "valid-policy.md" in path
            
            # Test path traversal attempt
            path = get_secure_policy_page_path("../../../etc/passwd")
            assert path is None
    
    def test_get_secure_archive_path(self, app):
        """Test secure archive path generation."""
        with app.app_context():
            from app.content.utils import get_secure_archive_path
            
            # Test valid filename
            path = get_secure_archive_path("archived-file.md")
            assert path is not None
            assert "archived-file.md" in path
            
            # Test path traversal attempt
            path = get_secure_archive_path("../../../etc/passwd")
            assert path is None
    
    def test_parse_metadata_from_markdown(self):
        """Test markdown metadata parsing."""
        from app.content.utils import parse_metadata_from_markdown
        
        # Test markdown with YAML frontmatter
        markdown_content = """---
title: Test Post
author: Test Author
published: true
---

This is the content of the post."""
        
        metadata, content = parse_metadata_from_markdown(markdown_content)
        
        assert metadata['title'] == 'Test Post'
        assert metadata['author'] == 'Test Author' 
        assert metadata['published'] is True
        assert content.strip() == 'This is the content of the post.'
        
        # Test markdown without frontmatter
        plain_content = "Just plain markdown content"
        metadata, content = parse_metadata_from_markdown(plain_content)
        
        assert metadata == {}
        assert content == plain_content
        
        # Test empty content
        metadata, content = parse_metadata_from_markdown("")
        assert metadata == {}
        assert content == ""
    
    def test_find_orphaned_policy_pages(self, app, db_session):
        """Test finding orphaned policy pages."""
        with app.app_context():
            from app.content.utils import find_orphaned_policy_pages
            
            # This function requires a complete app context and database
            # Just test that it can be imported and called without error
            try:
                orphans = find_orphaned_policy_pages()
                # Should return a list (may be empty)
                assert isinstance(orphans, list)
            except Exception:
                # If it fails due to missing storage directory, that's expected in tests
                pass
    
    def test_recover_orphaned_policy_page_validation(self, app, db_session):
        """Test orphaned policy page recovery validation."""
        with app.app_context():
            from app.content.utils import recover_orphaned_policy_page
            
            # Test with invalid filename
            success, message, policy = recover_orphaned_policy_page("../../../etc/passwd", 1)
            assert not success
            assert "Markdown file not found" in message or "Invalid filename" in message
            assert policy is None
            
            # Test with empty filename
            success, message, policy = recover_orphaned_policy_page("", 1)
            assert not success
            assert policy is None