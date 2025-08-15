"""
Unit tests for hero image functionality in content management.
"""
import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock

class TestHeroImageValidation:
    """Test cases for hero image validation functionality."""
    
    def test_validate_hero_image_selection_no_image(self, app):
        """Test validation with no hero image selected."""
        with app.app_context():
            from app.content.routes import validate_hero_image_selection
            from app.models import Post
            
            post = Post(title='Test Post', summary='Test')
            result = validate_hero_image_selection(None, post)
            assert result is True
            
            result = validate_hero_image_selection('', post)
            assert result is True
    
    def test_validate_hero_image_selection_newly_uploaded(self, app):
        """Test validation with newly uploaded images."""
        with app.app_context():
            from app.content.routes import validate_hero_image_selection
            from app.models import Post
            
            post = Post(title='Test Post', summary='Test')
            newly_uploaded = [
                {'filename': 'new_image.jpg', 'size': 1024},
                {'filename': 'another_image.png', 'size': 2048}
            ]
            
            # Valid newly uploaded image
            result = validate_hero_image_selection('new_image.jpg', post, newly_uploaded)
            assert result is True
            
            # Invalid image not in newly uploaded
            result = validate_hero_image_selection('nonexistent.jpg', post, newly_uploaded)
            assert result is False
    
    @patch('app.content.routes.get_post_existing_images')
    def test_validate_hero_image_selection_existing_images(self, mock_get_images, app):
        """Test validation with existing images."""
        with app.app_context():
            from app.content.routes import validate_hero_image_selection
            from app.models import Post
            
            # Mock existing images
            mock_get_images.return_value = ['existing1.jpg', 'existing2.png']
            
            post = Post(title='Test Post', summary='Test', directory_name='1-abc12345-test')
            
            # Valid existing image
            result = validate_hero_image_selection('existing1.jpg', post)
            assert result is True
            
            # Invalid image not in existing
            result = validate_hero_image_selection('nonexistent.jpg', post)
            assert result is False


class TestPostDirectoryCreation:
    """Test cases for post directory creation functionality."""
    
    @patch('os.makedirs')
    @patch('app.content.utils.current_app')
    def test_create_post_directory(self, mock_app, mock_makedirs, app):
        """Test post directory creation."""
        with app.app_context():
            from app.content.utils import create_post_directory
            
            # Mock configuration - use a mock object that returns the right value
            mock_config = MagicMock()
            mock_config.get.return_value = '/fake/posts/path'
            mock_app.config = mock_config
            
            # Test directory creation
            result = create_post_directory(1, 'Test Post Title')
            
            # Should return directory name with pattern: {post_id}-{uuid}-{slug}
            assert result.startswith('1-')
            assert result.endswith('-test-post-title')
            
            # Should create main directory and images subdirectory
            assert mock_makedirs.call_count == 2
    
    def test_slugify_title(self, app):
        """Test title slugification for directory names."""
        with app.app_context():
            from app.content.utils import slugify_title
            
            # Test basic slugification
            assert slugify_title('Test Post Title') == 'test-post-title'
            
            # Test with special characters
            assert slugify_title('Test & Special! Post') == 'test-special-post'
            
            # Test with maximum length
            long_title = 'This is a very long title that exceeds the maximum length limit'
            result = slugify_title(long_title, max_length=20)
            assert len(result) <= 20
            
            # Test empty title
            assert slugify_title('') == 'untitled'
            assert slugify_title(None) == 'untitled'
    
    @patch('os.path.exists')
    @patch('os.rename')
    @patch('app.content.utils.current_app')
    def test_rename_post_directory(self, mock_app, mock_rename, mock_exists, app):
        """Test renaming post directory when title changes."""
        with app.app_context():
            from app.content.utils import rename_post_directory
            
            # Mock configuration - use a mock object that returns the right value
            mock_config = MagicMock()
            mock_config.get.return_value = '/fake/posts/path'
            mock_app.config = mock_config
            mock_exists.side_effect = lambda path: 'old' in path  # Only old path exists
            
            old_directory = '1-abc12345-old-title'
            new_title = 'New Post Title'
            
            result = rename_post_directory(old_directory, new_title)
            
            # Should return new directory name
            assert result == '1-abc12345-new-post-title'
            
            # Should have called os.rename
            mock_rename.assert_called_once()
    
    def test_get_post_file_path_validation(self, app):
        """Test post file path validation."""
        with app.app_context():
            from app.content.utils import get_post_file_path
            
            with patch('app.content.utils.current_app') as mock_app:
                mock_config = MagicMock()
                mock_config.get.return_value = '/fake/posts/path'
                mock_app.config = mock_config
                
                # Valid directory pattern
                result = get_post_file_path('1-abc12345-test-post', 'file.md')
                assert result is not None
                
                # Invalid directory pattern (missing UUID)
                result = get_post_file_path('invalid-directory', 'file.md')
                assert result is None
                
                # Invalid directory pattern (wrong format)
                result = get_post_file_path('not-a-valid-format', 'file.md')
                assert result is None


class TestPostImageFunctionality:
    """Test cases for post image functionality."""
    
    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('app.content.utils.current_app')
    def test_get_post_existing_images(self, mock_app, mock_listdir, mock_exists, app):
        """Test getting existing images from post directory."""
        with app.app_context():
            from app.content.utils import get_post_existing_images
            
            # Mock configuration
            mock_config = MagicMock()
            mock_config.get.side_effect = lambda key, default=None: {
                'POSTS_STORAGE_PATH': '/fake/posts/path',
                'IMAGE_ALLOWED_TYPES': ['jpg', 'jpeg', 'png', 'gif']
            }.get(key, default)
            mock_app.config = mock_config
            
            mock_exists.return_value = True
            mock_listdir.return_value = [
                'image1.jpg',
                'image2.png', 
                'document.pdf',  # Should be filtered out
                'image3.jpeg',
                'text.txt'  # Should be filtered out
            ]
            
            result = get_post_existing_images('1-abc12345-test-post')
            
            # Should return only image files, sorted
            expected = ['image1.jpg', 'image2.png', 'image3.jpeg']
            assert result == expected
    
    def test_get_post_existing_images_no_directory(self, app):
        """Test getting images when directory doesn't exist."""
        with app.app_context():
            from app.content.utils import get_post_existing_images
            
            # Test with no directory name
            result = get_post_existing_images('')
            assert result == []
            
            result = get_post_existing_images(None)
            assert result == []
    
    @patch('app.content.utils.current_app')
    def test_get_post_image_path(self, mock_app, app):
        """Test getting secure image path for post."""
        with app.app_context():
            from app.content.utils import get_post_image_path
            
            # Mock configuration
            mock_config = MagicMock()
            mock_config.get.return_value = '/fake/posts/path'
            mock_app.config = mock_config
            
            # Valid directory and filename
            result = get_post_image_path('1-abc12345-test-post', 'image.jpg')
            assert result is not None
            assert 'images' in result
            assert 'image.jpg' in result
            
            # Invalid directory pattern
            result = get_post_image_path('invalid-directory', 'image.jpg')
            assert result is None


class TestContentFormValidation:
    """Test cases for content form validation with hero images."""
    
    def test_hero_image_form_field_exists(self, app):
        """Test that hero image field exists in WritePostForm."""
        with app.app_context():
            from app.content.forms import WritePostForm
            
            form = WritePostForm()
            assert hasattr(form, 'hero_image')
            assert form.hero_image is not None
    
    def test_hero_image_form_validation(self, app):
        """Test hero image form validation."""
        with app.app_context():
            from app.content.forms import WritePostForm
            
            form = WritePostForm()
            
            # Set up choices for validation
            form.hero_image.choices = [
                ('', 'No hero image'),
                ('image1.jpg', 'image1.jpg'),
                ('image2.png', 'image2.png')
            ]
            
            # Valid choice (empty)
            form.hero_image.data = ''
            assert form.validate_hero_image(form.hero_image) is None
            
            # Valid choice (existing image)
            form.hero_image.data = 'image1.jpg'
            assert form.validate_hero_image(form.hero_image) is None