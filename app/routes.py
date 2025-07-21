# Utility functions and decorators for Flask routes
# All route handlers have been migrated to appropriate blueprints:
# - Authentication routes: app/auth/routes.py
# - Main public routes: app/main/routes.py  
# - Admin routes: app/admin/routes.py
# - API routes: app/api/routes.py

from functools import wraps
import sqlalchemy as sa
from flask import current_app, abort
from flask_login import current_user
from app import db
from app.models import Member
from app.audit import audit_log_security_event


def admin_required(f):
    """
    Decorator to require admin privileges.
    Can be used in addition to @login_required.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if not current_user.is_admin:
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Non-admin user {current_user.username} attempted to access admin-only resource')
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def role_required(*required_roles):
    """
    Decorator to require specific roles.
    Usage: @role_required('Admin', 'User Manager')
    Can be used in addition to @login_required.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            
            # Admin users bypass role checks
            if current_user.is_admin:
                current_app.logger.info(f"Admin user {current_user.username} bypassing role check for {required_roles}")
                return f(*args, **kwargs)
            
            # Check if user has any of the required roles
            user_roles = [role.name for role in current_user.roles]
            current_app.logger.info(f"User {current_user.username} (admin: {current_user.is_admin}) has roles {user_roles}, checking against required roles {required_roles}")
            if not any(role in user_roles for role in required_roles):
                current_app.logger.warning(f"Access denied for user {current_user.username} with roles {user_roles} to resource requiring {required_roles}")
                audit_log_security_event('ACCESS_DENIED', 
                                       f'User {current_user.username} with roles {user_roles} attempted to access resource requiring roles {required_roles}')
                
                # Handle API requests with JSON response
                if request.path.startswith('/api/') or request.is_json or 'application/json' in request.headers.get('Accept', ''):
                    from flask import jsonify
                    return jsonify({
                        'success': False,
                        'error': f'Access denied. Required roles: {", ".join(required_roles)}'
                    }), 403
                else:
                    abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def _get_member_data(member, show_private_data=False):
    """
    Helper function to get member data with optional privacy filtering.
    
    This is the single source of truth for member data formatting. It ensures
    consistent behavior across all routes while allowing admin/User Manager
    access to all data and respecting privacy settings for regular users.
    
    Args:
        member: Member object from database
        show_private_data: Boolean - True for admins/User Managers, False for regular users
    
    Returns:
        Dictionary with member data, filtered according to privacy settings
    """
    base_data = {
        'id': member.id,
        'firstname': member.firstname,
        'lastname': member.lastname,
        'status': member.status
    }
    
    # Add email if it should be shared or if requester has admin privileges
    if show_private_data or member.share_email:
        base_data['email'] = member.email
    
    # Add phone if it should be shared or if requester has admin privileges  
    if show_private_data or member.share_phone:
        base_data['phone'] = member.phone
    
    # Admin-only fields
    if show_private_data:
        base_data.update({
            'username': member.username,
            'gender': member.gender,
            'is_admin': member.is_admin,
            'share_email': member.share_email,
            'share_phone': member.share_phone,
            'last_login': member.last_login.isoformat() if member.last_login else None,
            'lockout': member.lockout
        })
    
    return base_data


def _search_members_base(query):
    """
    Helper function for member search functionality.
    Returns SQLAlchemy query results.
    """
    if not query:
        return db.session.scalars(sa.select(Member).where(
            Member.status.in_(['Full', 'Life', 'Social'])
        ).order_by(Member.firstname)).all()
    
    return db.session.scalars(sa.select(Member).where(sa.and_(
        Member.status.in_(['Full', 'Life', 'Social']),
        sa.or_(
            Member.username.ilike(f'%{query}%'),
            Member.firstname.ilike(f'%{query}%'),
            Member.lastname.ilike(f'%{query}%'),
            Member.email.ilike(f'%{query}%')
        )
    )).order_by(Member.firstname)).all()