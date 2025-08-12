"""
Audit Logging System for Database Operations

This module provides comprehensive audit logging for all database changes in the bowls club application.
Every database modification (create, update, delete) is logged with timestamp, user, and operation details.

Usage:
    from app.audit import audit_log_create, audit_log_update, audit_log_delete
    
    # For new records
    audit_log_create('Member', new_member.id, f'Created member: {new_member.username}')
    
    # For updates
    audit_log_update('Member', member.id, f'Updated member: {member.username}', {'email': 'old@example.com'})
    
    # For deletions
    audit_log_delete('Member', member_id, f'Deleted member: {username}')
"""

import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, Union
from flask import current_app
from flask_login import current_user


# Configure audit logger
def setup_audit_logger():
    """Setup and configure the audit logger with proper formatting and file handling."""
    # Create audit logger
    audit_logger = logging.getLogger('audit')
    audit_logger.setLevel(logging.INFO)
    
    # Prevent duplicate log entries
    if audit_logger.hasHandlers():
        return audit_logger
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(current_app.instance_path, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Create file handler for audit.log
    log_file = os.path.join(log_dir, 'audit.log')
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    
    # Add handler to logger
    audit_logger.addHandler(file_handler)
    
    # Prevent propagation to root logger
    audit_logger.propagate = False
    
    return audit_logger


def get_current_user_info() -> str:
    """Get current user information for audit logging."""
    if current_user.is_authenticated:
        return f"{current_user.username} (ID: {current_user.id})"
    return "SYSTEM"


def audit_log_create(model_name: str, record_id: Union[int, str], description: str, 
                    additional_data: Optional[Dict[str, Any]] = None):
    """
    Log database record creation.
    
    Args:
        model_name: Name of the database model (e.g., 'Member', 'Post', 'Event')
        record_id: ID of the created record
        description: Human-readable description of the operation
        additional_data: Optional additional data to include in the log
    """
    try:
        logger = setup_audit_logger()
        user_info = get_current_user_info()
        
        log_message = f"CREATE | {model_name} | ID: {record_id} | User: {user_info} | {description}"
        
        logger.info(log_message)
    except Exception as e:
        # Audit logging should never break application functionality
        # But we should still log the failure for debugging
        try:
            # Try to log the audit logging failure itself
            fallback_logger = setup_audit_logger()
            fallback_logger.error(f"AUDIT_FAILURE | Failed to log CREATE for {model_name} ID {record_id}: {str(e)}")
        except Exception:
            # If even the fallback fails, don't crash the application
            pass


def audit_log_update(model_name: str, record_id: Union[int, str], description: str,
                    changes: Optional[Dict[str, Any]] = None, 
                    additional_data: Optional[Dict[str, Any]] = None):
    """
    Log database record updates.
    
    Args:
        model_name: Name of the database model (e.g., 'Member', 'Post', 'Event')
        record_id: ID of the updated record
        description: Human-readable description of the operation
        changes: Optional dictionary of field changes {'field': 'old_value'}
        additional_data: Optional additional data to include in the log
    """
    logger = setup_audit_logger()
    user_info = get_current_user_info()
    
    log_message = f"UPDATE | {model_name} | ID: {record_id} | User: {user_info} | {description}"
    
    logger.info(log_message)


def audit_log_delete(model_name: str, record_id: Union[int, str], description: str,
                    additional_data: Optional[Dict[str, Any]] = None):
    """
    Log database record deletion.
    
    Args:
        model_name: Name of the database model (e.g., 'Member', 'Post', 'Event')
        record_id: ID of the deleted record
        description: Human-readable description of the operation
        additional_data: Optional additional data to include in the log
    """
    logger = setup_audit_logger()
    user_info = get_current_user_info()
    
    log_message = f"DELETE | {model_name} | ID: {record_id} | User: {user_info} | {description}"
    
    logger.info(log_message)


def audit_log_bulk_operation(operation: str, model_name: str, count: int, description: str,
                           additional_data: Optional[Dict[str, Any]] = None):
    """
    Log bulk database operations (e.g., bulk imports, bulk updates).
    
    Args:
        operation: Type of operation ('BULK_CREATE', 'BULK_UPDATE', 'BULK_DELETE')
        model_name: Name of the database model
        count: Number of records affected
        description: Human-readable description of the operation
        additional_data: Optional additional data to include in the log
    """
    logger = setup_audit_logger()
    user_info = get_current_user_info()
    
    log_message = f"{operation} | {model_name} | Count: {count} | User: {user_info} | {description}"
    
    logger.info(log_message)


def audit_log_authentication(event_type: str, username: str, success: bool, 
                           additional_data: Optional[Dict[str, Any]] = None):
    """
    Log authentication events.
    
    Args:
        event_type: Type of authentication event ('LOGIN', 'LOGOUT', 'PASSWORD_RESET')
        username: Username involved in the event
        success: Whether the operation was successful
        additional_data: Optional additional data to include in the log
    """
    logger = setup_audit_logger()
    
    status = "SUCCESS" if success else "FAILURE"
    log_message = f"AUTH | {event_type} | {status} | User: {username}"
    
    logger.info(log_message)


def audit_log_security_event(event_type: str, description: str, 
                           additional_data: Optional[Dict[str, Any]] = None):
    """
    Log security-related events.
    
    Args:
        event_type: Type of security event ('ACCESS_DENIED', 'INVALID_TOKEN', 'SUSPICIOUS_ACTIVITY')
        description: Human-readable description of the event
        additional_data: Optional additional data to include in the log
    """
    logger = setup_audit_logger()
    user_info = get_current_user_info()
    
    log_message = f"SECURITY | {event_type} | User: {user_info} | {description}"
    
    logger.warning(log_message)


def audit_log_system_event(event_type: str, description: str,
                         additional_data: Optional[Dict[str, Any]] = None):
    """
    Log system-level events.
    
    Args:
        event_type: Type of system event ('STARTUP', 'SHUTDOWN', 'MIGRATION', 'BACKUP')
        description: Human-readable description of the event
        additional_data: Optional additional data to include in the log
    """
    logger = setup_audit_logger()
    
    log_message = f"SYSTEM | {event_type} | {description}"
    
    logger.info(log_message)


def audit_log_file_operation(operation: str, filename: str, description: str,
                           additional_data: Optional[Dict[str, Any]] = None):
    """
    Log file operations (uploads, deletions, moves).
    
    Args:
        operation: Type of file operation ('UPLOAD', 'DELETE', 'MOVE')
        filename: Name of the file involved
        description: Human-readable description of the operation
        additional_data: Optional additional data to include in the log
    """
    logger = setup_audit_logger()
    user_info = get_current_user_info()
    
    log_message = f"FILE | {operation} | File: {filename} | User: {user_info} | {description}"
    
    logger.info(log_message)


def get_model_changes(model_instance, form_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Helper function to detect changes between model instance and form data.
    
    Args:
        model_instance: The database model instance
        form_data: Dictionary of new values from form
    
    Returns:
        Dictionary of changes with old values
    """
    changes = {}
    
    for field, new_value in form_data.items():
        if hasattr(model_instance, field):
            old_value = getattr(model_instance, field)
            if old_value != new_value:
                changes[field] = str(old_value) if old_value is not None else None
    
    return changes