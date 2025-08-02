# Admin routes for the Bowls Club application
from datetime import datetime, timedelta, date
from flask import render_template, flash, redirect, url_for, request, current_app, jsonify
from flask_login import login_required, current_user
from functools import wraps
import sqlalchemy as sa
import os

from app.admin import bp
from app import db
from app.models import Member, Role, Event, Booking, Pool, PoolRegistration
from app.audit import audit_log_create, audit_log_update, audit_log_delete, audit_log_security_event, get_model_changes
from app.forms import FlaskForm
from app.routes import role_required
from app.events.utils import can_user_manage_event

def admin_required(f):
    """
    Decorator to restrict access to admin-only routes.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if not current_user.is_admin:
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Non-admin user {current_user.username} attempted to access admin route')
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


# manage_members route moved to app/members/routes.py


# edit_member route moved to app/members/routes.py


# admin_reset_password (reset_member_password) route moved to app/members/routes.py


# import_users route moved to app/members/routes.py


# manage_roles route moved to app/members/routes.py








# REMOVED: Legacy admin event management - migrated to events blueprint
# Use events.list_events and events.manage_event instead


# REMOVED: Duplicate of events.toggle_event_pool - use events blueprint instead


# MOVED: create_event_pool moved to pools.admin_create_event_pool












# MOVED TO BOOKINGS BLUEPRINT: edit_booking functionality moved to /bookings/admin/edit/<id>




# Event team editing removed - teams are now created from pools via bookings


# Event team creation removed - teams are now created from pools via bookings


# Event team deletion removed - teams are now managed via bookings


# Team creation from pool removed - teams are now created from pools via individual bookings



# Team copying to bookings removed - bookings now create teams directly from pools


# REMOVED: Duplicate of teams.add_substitute - use teams blueprint instead


# REMOVED: Duplicate of teams.update_member_availability - use teams blueprint instead


# MOVED: auto_select_pool_members moved to pools.admin_auto_select_pool_members


# MOVED: manage_teams moved to bookings.admin_manage_teams


# add_user_to_role route moved to app/members/routes.py


# remove_user_from_role route moved to app/members/routes.py


# MOVED: add_member_to_pool moved to pools.admin_add_member_to_pool


# MOVED: delete_from_pool moved to pools.admin_delete_from_pool
