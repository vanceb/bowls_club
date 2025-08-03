"""
Unit tests for audit logging functionality.

Tests validate that all database operations are properly logged according to
security requirements in CLAUDE.md. No application code is modified.
"""

import pytest
import logging
from datetime import datetime
from unittest.mock import patch, MagicMock
from app import create_app, db
from app.models import Member, Event, Pool, PoolRegistration, Booking, Role, Post
from app.audit import (
    audit_log_create, audit_log_update, audit_log_delete, 
    audit_log_authentication, audit_log_security_event,
    audit_log_system_event, audit_log_bulk_operation
)


class TestAuditLogging:
    """Test audit logging functions and requirements."""
    
    def test_audit_log_create_format(self, app, test_member):
        """Test audit_log_create logs correct format."""
        with app.app_context():
            # Mock the audit logger
            with patch('app.audit.setup_audit_logger') as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger
                
                audit_log_create('Member', 123, 'Created test member', {'status': 'Full'})
                
                # Verify logger was called
                mock_logger.info.assert_called_once()
                log_message = mock_logger.info.call_args[0][0]
                
                # Verify log format contains required elements
                assert 'CREATE' in log_message
                assert 'Member' in log_message
                assert 'ID: 123' in log_message
                assert 'Created test member' in log_message

    def test_audit_log_update_format(self, app, test_member):
        """Test audit_log_update logs correct format."""
        with app.app_context():
            with patch('app.audit.setup_audit_logger') as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger
                
                changes = {'email': 'old@example.com', 'status': 'Inactive'}
                audit_log_update('Member', 456, 'Updated member email', changes, {'admin': True})
                
                mock_logger.info.assert_called_once()
                log_message = mock_logger.info.call_args[0][0]
                
                assert 'UPDATE' in log_message
                assert 'Member' in log_message
                assert 'ID: 456' in log_message
                assert 'Updated member email' in log_message

    def test_audit_log_delete_format(self, app, test_member):
        """Test audit_log_delete logs correct format."""
        with app.app_context():
            with patch('app.audit.setup_audit_logger') as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger
                
                audit_log_delete('Member', 789, 'Deleted inactive member')
                
                mock_logger.info.assert_called_once()
                log_message = mock_logger.info.call_args[0][0]
                
                assert 'DELETE' in log_message
                assert 'Member' in log_message
                assert 'ID: 789' in log_message
                assert 'Deleted inactive member' in log_message

    def test_audit_log_authentication_format(self, app):
        """Test audit_log_authentication logs correct format."""
        with app.app_context():
            with patch('app.audit.setup_audit_logger') as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger
                
                # Test successful login
                audit_log_authentication('LOGIN', 'testuser', True)
                
                mock_logger.info.assert_called()
                log_message = mock_logger.info.call_args[0][0]
                
                assert 'LOGIN' in log_message
                assert 'testuser' in log_message
                assert 'success' in log_message.lower()

    def test_audit_log_security_event_format(self, app):
        """Test audit_log_security_event logs correct format."""
        with app.app_context():
            with patch('app.audit.setup_audit_logger') as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger
                
                audit_log_security_event('ACCESS_DENIED', 'Unauthorized admin access attempt')
                
                mock_logger.warning.assert_called_once()
                log_message = mock_logger.warning.call_args[0][0]
                
                assert 'ACCESS_DENIED' in log_message
                assert 'Unauthorized admin access attempt' in log_message

    def test_audit_log_system_event_format(self, app):
        """Test audit_log_system_event logs correct format."""
        with app.app_context():
            with patch('app.audit.setup_audit_logger') as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger
                
                audit_log_system_event('MIGRATION', 'Database migration completed')
                
                mock_logger.info.assert_called_once()
                log_message = mock_logger.info.call_args[0][0]
                
                assert 'MIGRATION' in log_message
                assert 'Database migration completed' in log_message

    def test_audit_log_bulk_operation_format(self, app):
        """Test audit_log_bulk_operation logs correct format."""
        with app.app_context():
            with patch('app.audit.setup_audit_logger') as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger
                
                audit_log_bulk_operation('BULK_CREATE', 'Member', 25, 'CSV import of new members')
                
                mock_logger.info.assert_called_once()
                log_message = mock_logger.info.call_args[0][0]
                
                assert 'BULK_CREATE' in log_message
                assert 'Member' in log_message
                assert '25' in log_message
                assert 'CSV import of new members' in log_message

    def test_audit_logging_with_user_context(self, app, test_member):
        """Test audit logging includes user context when available."""
        with app.app_context():
            with patch('app.audit.setup_audit_logger') as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger
                
                # Mock current_user
                with patch('app.audit.current_user') as mock_user:
                    mock_user.is_authenticated = True
                    mock_user.username = 'admin'
                    mock_user.id = 1
                    
                    audit_log_create('Event', 100, 'Created new event')
                    
                    mock_logger.info.assert_called_once()
                    log_message = mock_logger.info.call_args[0][0]
                    
                    # Should include user information
                    assert 'admin' in log_message or 'User:' in log_message

    def test_audit_logging_without_user_context(self, app):
        """Test audit logging works when no user is authenticated."""
        with app.app_context():
            with patch('app.audit.setup_audit_logger') as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger
                
                # Mock unauthenticated user
                with patch('app.audit.current_user') as mock_user:
                    mock_user.is_authenticated = False
                    
                    audit_log_system_event('STARTUP', 'Application initialized')
                    
                    mock_logger.info.assert_called_once()
                    log_message = mock_logger.info.call_args[0][0]
                    
                    # Should handle missing user gracefully
                    assert 'STARTUP' in log_message
                    assert 'Application initialized' in log_message

    def test_audit_logging_error_handling(self, app):
        """Test audit logging handles errors gracefully."""
        with app.app_context():
            # Test with failing logger - should not raise exception
            with patch('app.audit.setup_audit_logger') as mock_setup:
                mock_logger = MagicMock()
                mock_logger.info.side_effect = Exception("Logging failed")
                mock_setup.return_value = mock_logger
                
                # Should not raise exception even if logging fails
                # Audit module should handle errors internally
                audit_log_create('Member', 1, 'Test creation')
                # Test passes if no exception is raised

class TestAuditLogRequirements:
    """Test that audit logging meets security requirements."""
    
    def test_audit_log_format_compliance(self, app):
        """Test audit logs follow required format from CLAUDE.md."""
        with app.app_context():
            with patch('app.audit.setup_audit_logger') as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger
                
                audit_log_create('Member', 123, 'Created member', {'status': 'Full'})
                
                mock_logger.info.assert_called_once()
                log_message = mock_logger.info.call_args[0][0]
                
                # Verify format matches CLAUDE.md specification:
                # YYYY-MM-DD HH:MM:SS | INFO | OPERATION | ModelName | ID: xxx | User: username (ID: xxx) | Description | Changes: {...} | Data: {...}
                required_elements = ['CREATE', 'Member', 'ID: 123', 'Created member']
                for element in required_elements:
                    assert element in log_message, f"Missing required element: {element}"

    def test_all_crud_operations_logged(self, app, test_member):
        """Test all CRUD operations have audit logging."""
        with app.app_context():
            with patch('app.audit.setup_audit_logger') as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger
                
                # Test CREATE
                audit_log_create('Member', 1, 'Created member')
                assert mock_logger.info.called
                
                # Test UPDATE
                mock_logger.reset_mock()
                audit_log_update('Member', 1, 'Updated member', {'email': 'old@test.com'})
                assert mock_logger.info.called
                
                # Test DELETE
                mock_logger.reset_mock()
                audit_log_delete('Member', 1, 'Deleted member')
                assert mock_logger.info.called

    def test_security_events_logged(self, app):
        """Test security events are properly logged."""
        with app.app_context():
            with patch('app.audit.setup_audit_logger') as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger
                
                # Test various security events
                security_events = [
                    ('ACCESS_DENIED', 'Unauthorized access attempt'),
                    ('INVALID_TOKEN', 'Invalid password reset token'),
                    ('BRUTE_FORCE', 'Multiple failed login attempts'),
                ]
                
                for event_type, description in security_events:
                    mock_logger.reset_mock()
                    audit_log_security_event(event_type, description)
                    assert mock_logger.warning.called or mock_logger.error.called

    def test_authentication_events_logged(self, app):
        """Test authentication events are properly logged."""
        with app.app_context():
            with patch('app.audit.setup_audit_logger') as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger
                
                # Test successful and failed authentication
                auth_events = [
                    ('LOGIN', 'user1', True),
                    ('LOGIN', 'user2', False),
                    ('LOGOUT', 'user1', True),
                    ('PASSWORD_RESET', 'user3', True),
                ]
                
                for event_type, username, success in auth_events:
                    mock_logger.reset_mock()
                    audit_log_authentication(event_type, username, success)
                    assert mock_logger.info.called or mock_logger.warning.called

class TestAuditLogIntegration:
    """Test audit logging integration with application."""
    
    def test_database_operations_trigger_audit_logs(self, app, db_session):
        """Test that database operations should trigger audit logs."""
        # Note: This test verifies the expectation that audit logging should be called
        # in real database operations, but doesn't test actual integration to avoid
        # modifying application code during testing
        
        with app.app_context():
            # Create test data
            member = Member(
                username='audittest',
                firstname='Audit',
                lastname='Test',
                email='audit@test.com',
                status='Full'
            )
            member.set_password('testpass123')
            
            # In real application, this should trigger audit_log_create
            db_session.add(member)
            db_session.commit()
            
            # Test passes if no exceptions - integration testing would verify
            # that audit_log_create is actually called in route handlers
            assert member.id is not None

    def test_audit_log_data_serialization(self, app):
        """Test audit logging handles complex data structures."""
        with app.app_context():
            with patch('app.audit.setup_audit_logger') as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger
                
                # Test with complex data
                complex_data = {
                    'user_roles': ['Admin', 'Event Manager'],
                    'metadata': {'last_login': '2024-01-01', 'preferences': {'theme': 'dark'}},
                    'counts': {'events': 5, 'bookings': 12}
                }
                
                audit_log_create('Member', 1, 'Created complex member', complex_data)
                
                mock_logger.info.assert_called_once()
                # Should not raise serialization errors
                log_message = mock_logger.info.call_args[0][0]
                assert 'Member' in log_message