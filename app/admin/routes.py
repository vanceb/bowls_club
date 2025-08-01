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


@bp.route('/toggle_event_pool/<int:event_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def toggle_event_pool(event_id):
    """
    Toggle pool registration status for an event (open/close)
    """
    try:
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        event = db.session.get(Event, event_id)
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check permissions - must be able to manage this specific event
        if not can_user_manage_event(current_user, event):
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to toggle pool for event {event_id}')
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check if event has pool enabled
        if not event.has_pool_enabled():
            flash('This event does not have pool registration enabled.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Toggle pool status
        if event.pool.is_open:
            event.pool.close_pool()
            flash(f'Pool registration for "{event.name}" has been closed.', 'info')
            action = 'closed'
        else:
            event.pool.reopen_pool()
            flash(f'Pool registration for "{event.name}" has been reopened.', 'success')
            action = 'reopened'
        
        db.session.commit()
        
        # Audit log
        audit_log_update('Pool', event.pool.id, 
                        f'Pool registration {action} for event: {event.name}')
        
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        current_app.logger.error(f"Error toggling event pool: {str(e)}")
        flash('An error occurred while updating pool status.', 'error')
        return redirect(url_for('admin.manage_events'))


@bp.route('/create_event_pool/<int:event_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def create_event_pool(event_id):
    """
    Create a new pool for an event
    """
    try:
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        event = db.session.get(Event, event_id)
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check permissions - must be able to manage this specific event
        if not can_user_manage_event(current_user, event):
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to create pool for event {event_id}')
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check if event already has a pool
        if event.has_pool_enabled():
            flash('This event already has pool registration enabled.', 'warning')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Create new pool
        new_pool = Pool(
            event_id=event_id,
            is_open=True
        )
        
        # Enable pool on event
        event.has_pool = True
        
        db.session.add(new_pool)
        db.session.commit()
        
        # Audit log
        audit_log_create('Pool', new_pool.id, 
                        f'Created pool for event: {event.name}')
        
        flash(f'Pool registration has been enabled for "{event.name}".', 'success')
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        current_app.logger.error(f"Error creating event pool: {str(e)}")
        flash('An error occurred while creating the pool.', 'error')
        return redirect(url_for('admin.manage_events'))












# MOVED TO BOOKINGS BLUEPRINT: edit_booking functionality moved to /bookings/admin/edit/<id>




# Event team editing removed - teams are now created from pools via bookings


# Event team creation removed - teams are now created from pools via bookings


# Event team deletion removed - teams are now managed via bookings


# Team creation from pool removed - teams are now created from pools via individual bookings



# Team copying to bookings removed - bookings now create teams directly from pools


@bp.route('/add_substitute_to_team/<int:booking_team_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def add_substitute_to_team(booking_team_id):
    """
    Add a substitute to a booking team
    """
    try:
        from app.models import BookingTeam, BookingTeamMember
        from app.audit import audit_log_create
        
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        booking_team = db.session.get(BookingTeam, booking_team_id)
        if not booking_team:
            flash('Team not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        member_id = request.form.get('member_id', type=int)
        position = request.form.get('position', '')
        
        if not member_id or not position:
            flash('Member and position are required.', 'error')
            return redirect(url_for('admin.manage_events', event_id=booking_team.booking.event_id))
        
        # Check if member is already in the team
        existing = db.session.scalar(
            sa.select(BookingTeamMember).where(
                BookingTeamMember.booking_team_id == booking_team_id,
                BookingTeamMember.member_id == member_id
            )
        )
        
        if existing:
            flash('Member is already in this team.', 'warning')
            return redirect(url_for('admin.manage_events', event_id=booking_team.booking.event_id))
        
        # Add substitute
        substitute = BookingTeamMember(
            booking_team_id=booking_team_id,
            member_id=member_id,
            position=position,
            is_substitute=True,
            availability_status='pending'
        )
        
        db.session.add(substitute)
        db.session.commit()
        
        # Get member name for feedback
        member = db.session.get(Member, member_id)
        member_name = f"{member.firstname} {member.lastname}" if member else "Unknown"
        
        # Audit log
        audit_log_create('BookingTeamMember', substitute.id,
                        f'Added substitute {member_name} to team {booking_team.team_name}',
                        {'position': position, 'is_substitute': True})
        
        flash(f'Added {member_name} as substitute {position} to {booking_team.team_name}.', 'success')
        return redirect(url_for('admin.manage_events', event_id=booking_team.booking.event_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding substitute: {str(e)}")
        flash('An error occurred while adding the substitute.', 'error')
        return redirect(url_for('admin.manage_events'))


@bp.route('/update_member_availability/<int:booking_team_member_id>', methods=['POST'])
@login_required
def update_member_availability(booking_team_member_id):
    """
    Update a team member's availability status (accessible to team members and admins)
    """
    try:
        from app.models import BookingTeamMember
        from app.audit import audit_log_update
        
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('main.index'))
        
        booking_team_member = db.session.get(BookingTeamMember, booking_team_member_id)
        if not booking_team_member:
            flash('Team member not found.', 'error')
            return redirect(url_for('main.index'))
        
        # Check permission - member can update their own availability
        if not current_user.is_admin and current_user.id != booking_team_member.member_id:
            flash('You can only update your own availability.', 'error')
            return redirect(url_for('main.index'))
        
        new_status = request.form.get('status')
        if new_status not in ['pending', 'available', 'unavailable']:
            flash('Invalid status.', 'error')
            return redirect(url_for('main.index'))
        
        old_status = booking_team_member.availability_status
        booking_team_member.availability_status = new_status
        
        if new_status != 'pending':
            booking_team_member.confirmed_at = datetime.utcnow()
        
        db.session.commit()
        
        # Audit log
        audit_log_update('BookingTeamMember', booking_team_member.id,
                        f'Availability updated from {old_status} to {new_status}',
                        {'old_status': old_status, 'new_status': new_status})
        
        flash(f'Availability updated to {new_status}.', 'success')
        return redirect(url_for('main.index'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating availability: {str(e)}")
        flash('An error occurred while updating availability.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/auto_select_pool_members/<int:event_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def auto_select_pool_members(event_id):
    """
    Automatically select pool members for team creation based on criteria
    """
    try:
        from app.audit import audit_log_bulk_operation
        
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        event = db.session.get(Event, event_id)
        if not event or not event.has_pool_enabled():
            flash('Event not found or pool not enabled.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check permissions - must be able to manage this specific event
        if not can_user_manage_event(current_user, event):
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to auto-select pool members for event {event_id}')
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        selection_method = request.form.get('method', 'oldest_first')
        num_to_select = request.form.get('count', type=int)
        
        if not num_to_select or num_to_select <= 0:
            flash('Invalid selection count.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Get all registered members (all pool registrations are active)
        registered_members = list(event.pool.registrations)
        
        if len(registered_members) < num_to_select:
            flash(f'Only {len(registered_members)} registered members available, cannot select {num_to_select}.', 'warning')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Apply selection method
        if selection_method == 'oldest_first':
            selected_registrations = sorted(registered_members, key=lambda r: r.registered_at)[:num_to_select]
        elif selection_method == 'random':
            import random
            selected_registrations = random.sample(registered_members, num_to_select)
        else:
            # Default to oldest first
            selected_registrations = sorted(registered_members, key=lambda r: r.registered_at)[:num_to_select]
        
        # Pool status no longer tracked - all registered members are available for team creation
        flash(f'Pool members are always available for team creation. Use "Create Teams from Pool" instead.', 'info')
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in auto pool selection: {str(e)}")
        flash('An error occurred during automatic selection.', 'error')
        return redirect(url_for('admin.manage_events'))


@bp.route('/manage_teams/<int:booking_id>', methods=['GET', 'POST'])
@login_required
@role_required('Event Manager')
def manage_teams(booking_id):
    """
    Admin interface for managing teams for a specific booking
    Accessible to admins and booking organizers
    """
    try:
        # Get the booking
        booking = db.session.get(Booking, booking_id)
        if not booking:
            flash('Booking not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check if user has permission to manage teams
        if not current_user.is_admin and booking.organizer_id != current_user.id:
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to manage teams for booking {booking_id}')
            flash('You do not have permission to manage teams for this booking.', 'error')
            return redirect(url_for('bookings.bookings'))
        
        from app.models import BookingTeam, BookingTeamMember
        
        # Get existing teams for this booking
        teams = db.session.scalars(
            sa.select(BookingTeam)
            .where(BookingTeam.booking_id == booking_id)
            .order_by(BookingTeam.team_name)
        ).all()
        
        # Handle POST request for team management
        if request.method == 'POST':
            csrf_form = FlaskForm()
            if not csrf_form.validate_on_submit():
                flash('Security validation failed.', 'error')
                return redirect(url_for('bookings.admin_manage_teams', booking_id=booking_id))
            
            # Handle different actions
            action = request.form.get('action')
            
            if action == 'add_team':
                team_name = request.form.get('team_name')
                if team_name:
                    new_team = BookingTeam(
                        booking_id=booking_id,
                        team_name=team_name,
                        event_team_id=booking.event.teams[0].id if booking.event and booking.event.teams else None
                    )
                    db.session.add(new_team)
                    db.session.commit()
                    
                    audit_log_create('BookingTeam', new_team.id, 
                                   f'Added team {team_name} to booking {booking_id}')
                    flash(f'Team "{team_name}" added successfully.', 'success')
                else:
                    flash('Team name is required.', 'error')
            
            elif action == 'substitute_player':
                from app.audit import audit_log_update
                from datetime import datetime
                import json
                
                booking_team_member_id = request.form.get('booking_team_member_id')
                new_member_id = request.form.get('new_member_id')
                reason = request.form.get('reason', 'No reason provided')
                
                if booking_team_member_id and new_member_id:
                    booking_team_member = db.session.get(BookingTeamMember, int(booking_team_member_id))
                    new_member = db.session.get(Member, int(new_member_id))
                    
                    if booking_team_member and new_member:
                        # Get original player info before substitution
                        original_player_name = f"{booking_team_member.member.firstname} {booking_team_member.member.lastname}"
                        substitute_player_name = f"{new_member.firstname} {new_member.lastname}"
                        position = booking_team_member.position
                        original_member_id = booking_team_member.member_id
                        
                        # Log the substitution
                        substitution_log_entry = {
                            'timestamp': datetime.utcnow().isoformat(),
                            'action': 'substitution',
                            'original_player': original_player_name,
                            'substitute_player': substitute_player_name,
                            'position': position,
                            'made_by': f"{current_user.firstname} {current_user.lastname}",
                            'reason': reason
                        }
                        
                        # Update the booking team member
                        booking_team_member.member_id = new_member.id
                        booking_team_member.is_substitute = True
                        booking_team_member.substituted_at = datetime.utcnow()
                        booking_team_member.availability_status = 'pending'  # New player needs to confirm
                        
                        # Update substitution log on the team
                        booking_team = booking_team_member.booking_team
                        current_log = json.loads(booking_team.substitution_log or '[]')
                        current_log.append(substitution_log_entry)
                        booking_team.substitution_log = json.dumps(current_log)
                        
                        db.session.commit()
                        
                        # Audit log the substitution
                        audit_log_update('BookingTeamMember', booking_team_member.id, 
                                       f'Substituted {original_player_name} with {substitute_player_name} for {position}',
                                       {'original_member_id': original_member_id, 'new_member_id': new_member.id, 'reason': reason})
                        
                        flash(f'Successfully substituted {original_player_name} with {substitute_player_name} for {position}', 'success')
                    else:
                        flash('Invalid player selection for substitution.', 'error')
                else:
                    flash('Missing required information for substitution.', 'error')
            
            return redirect(url_for('bookings.admin_manage_teams', booking_id=booking_id))
        
        # Get session name
        sessions = current_app.config.get('DAILY_SESSIONS', {})
        session_name = sessions.get(booking.session, 'Unknown Session')
        
        # Get available members for substitutions 
        available_members = []
        if booking.event and booking.event.has_pool_enabled():
            # Get all pool members (all registrations are active)
            from app.models import PoolRegistration
            available_members = db.session.scalars(
                sa.select(Member)
                .join(PoolRegistration, Member.id == PoolRegistration.member_id)
                .where(PoolRegistration.pool_id == booking.event.pool.id)
                .order_by(Member.firstname, Member.lastname)
            ).all()
        else:
            # Fallback: get active members not already in the booking teams
            current_member_ids = {member.member_id for team in teams for member in team.booking_team_members}
            available_members = db.session.scalars(
                sa.select(Member)
                .where(Member.status.in_(['Full', 'Social', 'Life']))
                .where(~Member.id.in_(current_member_ids))
                .order_by(Member.firstname, Member.lastname)
            ).all()
        
        # Create CSRF form for template
        csrf_form = FlaskForm()
        
        return render_template('admin/manage_teams.html', 
                             booking=booking,
                             teams=teams,
                             session_name=session_name,
                             available_members=available_members,
                             csrf_form=csrf_form)
        
    except Exception as e:
        current_app.logger.error(f"Error managing teams for booking {booking_id}: {str(e)}")
        flash('An error occurred while managing teams.', 'error')
        return redirect(url_for('bookings.bookings'))


# add_user_to_role route moved to app/members/routes.py


# remove_user_from_role route moved to app/members/routes.py


@bp.route('/add_member_to_pool/<int:event_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def add_member_to_pool(event_id):
    """
    Add a member to the event pool (for Event Managers to expand the pool)
    """
    try:
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Get the event
        event = db.session.get(Event, event_id)
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check permissions - must be able to manage this specific event
        if not can_user_manage_event(current_user, event):
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to add member to pool for event {event_id}')
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check if event has pool enabled
        if not event.has_pool_enabled():
            flash('This event does not have pool registration enabled.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Get member_id from form
        member_id = request.form.get('member_id', type=int)
        if not member_id:
            flash('Please select a member to add.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Get the member
        member = db.session.get(Member, member_id)
        if not member:
            flash('Member not found.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Check if member is already in the pool
        existing_registration = event.pool.get_member_registration(member_id)
        if existing_registration and existing_registration.is_active:
            flash(f'{member.firstname} {member.lastname} is already registered for this event.', 'warning')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Add member to pool
        registration = PoolRegistration(
            pool_id=event.pool.id,
            member_id=member_id
        )
        db.session.add(registration)
        db.session.commit()
        
        # Audit log
        audit_log_create('PoolRegistration', registration.id, 
                        f'Event Manager added {member.firstname} {member.lastname} to pool for event: {event.name}')
        
        flash(f'{member.firstname} {member.lastname} added to event pool successfully!', 'success')
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        current_app.logger.error(f"Error adding member to pool: {str(e)}")
        flash('An error occurred while adding member to pool.', 'error')
        return redirect(url_for('admin.manage_events', event_id=event_id))


@bp.route('/delete_from_pool/<int:registration_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def delete_from_pool(registration_id):
    """
    Remove a member from the event pool entirely (admin version of user withdrawal)
    """
    try:
        from app.audit import audit_log_delete
        
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Get the registration
        registration = db.session.get(PoolRegistration, registration_id)
        if not registration:
            flash('Registration not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        event = registration.pool.event
        
        # Check permissions - must be able to manage this specific event
        if not can_user_manage_event(current_user, event):
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to delete pool registration {registration_id}')
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Store info for audit log and flash message
        member_name = f"{registration.member.firstname} {registration.member.lastname}"
        event_name = event.name
        event_id = event.id
        
        # Delete the registration entirely (same as user withdrawal)
        db.session.delete(registration)
        db.session.commit()
        
        # Audit log
        audit_log_delete('PoolRegistration', registration_id, 
                        f'Event Manager removed {member_name} from pool for event: {event_name}')
        
        flash(f'{member_name} removed from event pool successfully!', 'success')
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        current_app.logger.error(f"Error removing member from pool: {str(e)}")
        flash('An error occurred while removing member from pool.', 'error')
        return redirect(url_for('admin.manage_events'))


@bp.route('/test')
@login_required
@admin_required
def test():
    return "Admin routes are working!"