# Admin routes for the Bowls Club application
from datetime import datetime, timedelta, date
from flask import render_template, flash, redirect, url_for, request, current_app, jsonify
from flask_login import login_required, current_user
from functools import wraps
import sqlalchemy as sa
import os

from app.admin import bp
from app import db
from app.models import Member, Role, Event, Booking, EventPool, PoolRegistration
from app.audit import audit_log_create, audit_log_update, audit_log_delete, audit_log_security_event, get_model_changes
from app.forms import FlaskForm
from app.routes import role_required

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








@bp.route('/manage_events', methods=['GET', 'POST'])
@login_required
@role_required('Event Manager')
def manage_events():
    """
    Admin interface for managing events
    """
    try:
        from app.forms import EventForm, EventSelectionForm, BookingForm
        from app.models import EventTeam, Booking
        from app.audit import audit_log_create, audit_log_update
        
        # Get selected event ID from request
        selected_event_id = request.args.get('event_id', type=int) or request.form.get('event_id', type=int)
        selected_event = None
        event_teams = []
        event_bookings = []
        can_create_bookings = False
        
        # Initialize forms
        selection_form = EventSelectionForm()
        event_form = EventForm()
        booking_form = BookingForm()
        
        # Handle form submissions
        if request.method == 'POST':
            # Handle event creation/updating
            if 'submit' in request.form and event_form.validate_on_submit():
                if event_form.event_id.data:
                    # Update existing event
                    event = db.session.get(Event, event_form.event_id.data)
                    if event:
                        # Capture changes for audit log
                        changes = get_model_changes(event, {
                            'name': event_form.name.data,
                            'event_type': event_form.event_type.data,
                            'gender': event_form.gender.data,
                            'format': event_form.format.data,
                            'scoring': event_form.scoring.data
                        })
                        
                        # Update event
                        event.name = event_form.name.data
                        event.event_type = event_form.event_type.data
                        event.gender = event_form.gender.data
                        event.format = event_form.format.data
                        event.scoring = event_form.scoring.data
                        
                        # Update event managers
                        event.event_managers.clear()
                        for manager_id in event_form.event_managers.data:
                            manager = db.session.get(Member, manager_id)
                            if manager:
                                event.event_managers.append(manager)
                        
                        db.session.commit()
                        
                        # Audit log
                        audit_log_update('Event', event.id, f'Updated event: {event.name}', changes)
                        
                        flash(f'Event "{event.name}" updated successfully!', 'success')
                        selected_event_id = event.id
                else:
                    # Create new event
                    event = Event(
                        name=event_form.name.data,
                        event_type=event_form.event_type.data,
                        gender=event_form.gender.data,
                        format=event_form.format.data,
                        scoring=event_form.scoring.data
                    )
                    
                    # Add event managers
                    for manager_id in event_form.event_managers.data:
                        manager = db.session.get(Member, manager_id)
                        if manager:
                            event.event_managers.append(manager)
                    
                    db.session.add(event)
                    db.session.flush()  # Get event ID
                    
                    # Automatically create a pool for the new event (open by default)
                    event_pool = EventPool(
                        event_id=event.id,
                        is_open=True
                    )
                    event.has_pool = True
                    db.session.add(event_pool)
                    
                    db.session.commit()
                    
                    # Audit log
                    audit_log_create('Event', event.id, f'Created event: {event.name}')
                    audit_log_create('EventPool', event_pool.id, f'Auto-created pool for event: {event.name}')
                    
                    flash(f'Event "{event.name}" created successfully with pool registration open!', 'success')
                    selected_event_id = event.id
            
            # Handle booking creation/updating
            elif 'create_booking' in request.form and booking_form.validate_on_submit():
                if selected_event_id:
                    # Create new booking
                    booking = Booking(
                        booking_date=booking_form.booking_date.data,
                        session=booking_form.session.data,
                        organizer_id=current_user.id,
                        rink_count=booking_form.rink_count.data,
                        booking_type='event',
                        priority=booking_form.priority.data,
                        vs=booking_form.vs.data,
                        home_away=booking_form.home_away.data,
                        event_id=selected_event_id
                    )
                    
                    db.session.add(booking)
                    db.session.flush()  # Get booking ID
                    
                    # Copy event teams to booking teams if they exist
                    teams_copied = 0
                    members_copied = 0
                    event_teams = db.session.scalars(
                        sa.select(EventTeam).where(EventTeam.event_id == selected_event_id)
                    ).all()
                    
                    if event_teams:
                        from app.models import BookingTeam, BookingTeamMember
                        
                        for event_team in event_teams:
                            # Create booking team
                            booking_team = BookingTeam(
                                booking_id=booking.id,
                                event_team_id=event_team.id,
                                team_name=event_team.team_name,
                                team_number=event_team.team_number
                            )
                            db.session.add(booking_team)
                            db.session.flush()  # Get booking team ID
                            
                            # Copy team members
                            for team_member in event_team.team_members:
                                booking_team_member = BookingTeamMember(
                                    booking_team_id=booking_team.id,
                                    member_id=team_member.member_id,
                                    position=team_member.position,
                                    is_substitute=False,
                                    availability_status='pending'
                                )
                                db.session.add(booking_team_member)
                                members_copied += 1
                            
                            teams_copied += 1
                    
                    db.session.commit()
                    
                    # Audit log
                    if teams_copied > 0:
                        audit_log_create('Booking', booking.id, 
                                        f'Created event booking for {booking.booking_date} with {teams_copied} teams and {members_copied} members')
                    else:
                        audit_log_create('Booking', booking.id, f'Created event booking for {booking.booking_date}')
                    
                    if teams_copied > 0:
                        flash(f'Booking created successfully with {teams_copied} teams and {members_copied} members!', 'success')
                    else:
                        flash('Booking created successfully!', 'success')
        
        # Get selected event and related data
        if selected_event_id:
            selected_event = db.session.get(Event, selected_event_id)
            if selected_event:
                # Get event teams
                event_teams = db.session.scalars(
                    sa.select(EventTeam).where(EventTeam.event_id == selected_event_id)
                    .order_by(EventTeam.team_name)
                ).all()
                
                # Get event bookings
                event_bookings = db.session.scalars(
                    sa.select(Booking).where(Booking.event_id == selected_event_id)
                    .order_by(Booking.booking_date, Booking.session)
                ).all()
                
                # Check if we can create bookings (need at least one team)
                can_create_bookings = len(event_teams) > 0
                
                # Pre-populate event form with selected event data
                if request.method == 'GET':
                    event_form.event_id.data = selected_event.id
                    event_form.name.data = selected_event.name
                    event_form.event_type.data = selected_event.event_type
                    event_form.gender.data = selected_event.gender
                    event_form.format.data = selected_event.format
                    event_form.scoring.data = selected_event.scoring
                    event_form.event_managers.data = [manager.id for manager in selected_event.event_managers]
                
                # Set selection form to selected event
                selection_form.selected_event.data = selected_event_id
        
        # Get pool data if event has pool enabled
        pool_data = None
        pool_registrations = []
        if selected_event and selected_event.has_pool_enabled():
            pool_registrations = db.session.scalars(
                sa.select(PoolRegistration)
                .join(PoolRegistration.member)
                .where(PoolRegistration.pool_id == selected_event.pool.id)
                .order_by(Member.firstname, Member.lastname)
            ).all()
            
            pool_data = {
                'pool': selected_event.pool,
                'total_registrations': len(pool_registrations),
                'registered_count': len(pool_registrations),  # All registrations are 'registered' by existence
            }
        
        # Get team positions for display
        team_positions = current_app.config.get('TEAM_POSITIONS', {})
        
        # Get available members for adding to pool (members not already in the pool)
        available_members_for_pool = []
        if selected_event and selected_event.has_pool_enabled():
            # Get all active members
            all_members = db.session.scalars(
                sa.select(Member)
                .where(Member.status.in_(['Full', 'Social', 'Life']))
                .order_by(Member.firstname, Member.lastname)
            ).all()
            
            # Filter out members already in the pool
            pool_member_ids = set()
            if pool_registrations:
                pool_member_ids = {reg.member_id for reg in pool_registrations if reg.is_active}
            
            available_members_for_pool = [member for member in all_members if member.id not in pool_member_ids]
        
        return render_template('admin/manage_events.html', 
                             events=[], # Not used in template
                             selection_form=selection_form,
                             event_form=event_form,
                             booking_form=booking_form,
                             selected_event=selected_event,
                             event_teams=event_teams,
                             event_bookings=event_bookings,
                             can_create_bookings=can_create_bookings,
                             team_positions=team_positions,
                             pool_data=pool_data,
                             pool_registrations=pool_registrations,
                             available_members_for_pool=available_members_for_pool)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"Error in manage_events: {str(e)}")
        current_app.logger.error(f"Full traceback: {error_details}")
        current_app.logger.error(f"Request args: {request.args}")
        current_app.logger.error(f"Request form: {request.form}")
        flash(f'An error occurred while loading events: {str(e)}', 'error')
        return redirect(url_for('main.index'))


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
        audit_log_update('EventPool', event.pool.id, 
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
        
        # Check if event already has a pool
        if event.has_pool_enabled():
            flash('This event already has pool registration enabled.', 'warning')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Create new pool
        new_pool = EventPool(
            event_id=event_id,
            is_open=True
        )
        
        # Enable pool on event
        event.has_pool = True
        
        db.session.add(new_pool)
        db.session.commit()
        
        # Audit log
        audit_log_create('EventPool', new_pool.id, 
                        f'Created pool for event: {event.name}')
        
        flash(f'Pool registration has been enabled for "{event.name}".', 'success')
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        current_app.logger.error(f"Error creating event pool: {str(e)}")
        flash('An error occurred while creating the pool.', 'error')
        return redirect(url_for('admin.manage_events'))












@bp.route('/edit_booking/<int:booking_id>', methods=['GET', 'POST'])
@login_required
@role_required('Event Manager')
def edit_booking(booking_id):
    """
    Admin interface for editing existing bookings
    """
    try:
        from app.forms import BookingForm
        from app.utils import get_secure_post_path
        
        booking = db.session.get(Booking, booking_id)
        if not booking:
            flash('Booking not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        form = BookingForm(obj=booking)
        
        if form.validate_on_submit():
            # Capture changes for audit log
            changes = get_model_changes(booking, {
                'booking_date': form.booking_date.data,
                'session': form.session.data,
                'rink_count': form.rink_count.data,
                'priority': form.priority.data,
                'vs': form.vs.data,
                'home_away': form.home_away.data
            })
            
            # Update the booking with form data
            booking.booking_date = form.booking_date.data
            booking.session = form.session.data
            booking.rink_count = form.rink_count.data
            booking.priority = form.priority.data
            booking.vs = form.vs.data
            booking.home_away = form.home_away.data
            
            db.session.commit()
            
            # Audit log the booking edit
            audit_log_update('Booking', booking.id, f'Edited booking #{booking.id}', changes)
            
            flash('Booking updated successfully!', 'success')
            
            # Redirect back to events management if the booking has an event
            if booking.event_id:
                return redirect(url_for('admin.manage_events'))
            else:
                return redirect(url_for('main.bookings'))
        
        return render_template('admin/booking_form.html', 
                             form=form, 
                             booking=booking,
                             title=f"Edit Booking #{booking.id}")
        
    except Exception as e:
        current_app.logger.error(f"Error in edit_booking: {str(e)}")
        flash('An error occurred while editing the booking.', 'error')
        return redirect(url_for('admin.manage_events'))




@bp.route('/edit_event_team/<int:team_id>', methods=['GET', 'POST'])
@login_required
@role_required('Event Manager')
def edit_event_team(team_id):
    """
    Admin interface for editing event teams and assigning players to positions
    """
    try:
        from app.models import EventTeam, TeamMember
        from app.forms import create_team_member_form
        
        team = db.session.get(EventTeam, team_id)
        if not team:
            flash('Team not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check if user has permission to manage this event
        if not current_user.is_admin and current_user not in team.event.event_managers:
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Non-authorized user attempted to edit team {team_id}')
            flash('You do not have permission to edit this team.', 'error')
            return redirect(url_for('admin.manage_events', event_id=team.event.id))
        
        TeamMemberForm = create_team_member_form(team.event.format, team.event)
        form = TeamMemberForm()
        
        if form.validate_on_submit():
            try:
                # Capture existing team members for audit log
                existing_members = db.session.scalars(
                    sa.select(TeamMember).where(TeamMember.event_team_id == team.id)
                ).all()
                old_members = [f"{member.member.firstname} {member.member.lastname} ({member.position})" 
                              for member in existing_members]
                
                # Update team name
                old_team_name = team.team_name
                team.team_name = form.team_name.data
                
                # Build new team composition from form data
                team_positions = current_app.config.get('TEAM_POSITIONS', {})
                positions = team_positions.get(team.event.format, [])
                new_team_data = {}
                new_members = []
                
                for position in positions:
                    field_name = f"position_{position.lower().replace(' ', '_')}"
                    member_id = getattr(form, field_name).data
                    
                    if member_id and member_id > 0:  # Skip empty selections
                        new_team_data[position] = member_id
                        member_obj = db.session.get(Member, member_id)
                        if member_obj:
                            new_members.append(f"{member_obj.firstname} {member_obj.lastname} ({position})")
                
                # Validate no duplicate member assignments within this team
                all_member_ids = list(new_team_data.values())
                new_member_ids = set(all_member_ids)
                
                # Check for duplicates within the same team
                if len(all_member_ids) != len(new_member_ids):
                    # Find which members are duplicated
                    member_counts = {}
                    for member_id in all_member_ids:
                        member_counts[member_id] = member_counts.get(member_id, 0) + 1
                    
                    duplicated_members = []
                    for member_id, count in member_counts.items():
                        if count > 1:
                            member = db.session.get(Member, member_id)
                            if member:
                                duplicated_members.append(f"{member.firstname} {member.lastname} (assigned to {count} positions)")
                    
                    if duplicated_members:
                        flash(f'Cannot save team: {', '.join(duplicated_members)}', 'error')
                        # Re-populate form with existing data and return
                        form.team_name.data = team.team_name
                        for member in existing_members:
                            field_name = f"position_{member.position.lower().replace(' ', '_')}"
                            if hasattr(form, field_name):
                                getattr(form, field_name).data = member.member_id
                        return render_template('admin/edit_event_team.html',
                                             form=form,
                                             team=team,
                                             title=f"Edit {team.team_name}")
                
                # Validate no duplicate member assignments across all teams in the event
                if new_member_ids:
                    # Check for members assigned to other teams in this event (excluding current team)
                    other_team_members = db.session.scalars(
                        sa.select(TeamMember)
                        .join(EventTeam)
                        .where(EventTeam.event_id == team.event.id)
                        .where(EventTeam.id != team.id)  # Exclude current team
                        .where(TeamMember.member_id.in_(new_member_ids))
                    ).all()
                    
                    if other_team_members:
                        # Build error message with details
                        conflicts = {}
                        for tm in other_team_members:
                            member_name = f"{tm.member.firstname} {tm.member.lastname}"
                            team_name = tm.event_team.team_name
                            if member_name not in conflicts:
                                conflicts[member_name] = []
                            conflicts[member_name].append(team_name)
                        
                        error_details = []
                        for member_name, teams in conflicts.items():
                            error_details.append(f"{member_name} is already in {', '.join(teams)}")
                        
                        flash(f'Cannot save team: {'; '.join(error_details)}', 'error')
                        # Re-populate form with existing data and return
                        form.team_name.data = team.team_name
                        for member in existing_members:
                            field_name = f"position_{member.position.lower().replace(' ', '_')}"
                            if hasattr(form, field_name):
                                getattr(form, field_name).data = member.member_id
                        return render_template('admin/edit_event_team.html',
                                             form=form,
                                             team=team,
                                             title=f"Edit {team.team_name}")
                
                # Note: Pool registration status is no longer tracked - existence indicates registration
                # Team assignment is now tracked solely through BookingTeamMember relationships
                
                # Get current member IDs for logging purposes
                old_member_ids = {member.member_id for member in existing_members}
                
                if team.event.has_pool_enabled():
                    current_app.logger.info(f'Team update - Old members: {old_member_ids}, New members: {new_member_ids}')
                    current_app.logger.info(f'Pool members remain available for multiple bookings per event')
                
                # Only update team members if we have valid new data
                # Clear existing team members ONLY after we know new data is valid
                for member in existing_members:
                    db.session.delete(member)
                
                # Add new team members
                for position, member_id in new_team_data.items():
                    team_member = TeamMember(
                        event_team_id=team.id,
                        member_id=member_id,
                        position=position
                    )
                    db.session.add(team_member)
                
                # Commit all changes together
                db.session.commit()
                
                # Audit log the team update
                changes = {}
                if old_team_name != team.team_name:
                    changes['team_name'] = old_team_name
                changes['old_members'] = old_members
                changes['new_members'] = new_members
                
                audit_log_update('EventTeam', team.id, 
                                f'Updated team: {team.team_name} for event "{team.event.name}"', changes)
                
                flash(f'Team "{team.team_name}" updated successfully!', 'success')
                return redirect(url_for('admin.manage_events', event_id=team.event.id))
                
            except Exception as e:
                # Rollback transaction on any error to preserve existing data
                db.session.rollback()
                current_app.logger.error(f"Error updating team {team.id}: {str(e)}")
                flash('An error occurred while updating the team. No changes were made.', 'error')
        
        # Pre-populate form with existing data
        if request.method == 'GET':
            form.team_id.data = team.id
            form.team_name.data = team.team_name
            
            # Load existing team member assignments
            existing_members = db.session.scalars(
                sa.select(TeamMember).where(TeamMember.event_team_id == team.id)
            ).all()
            
            for member in existing_members:
                field_name = f"position_{member.position.lower().replace(' ', '_')}"
                if hasattr(form, field_name):
                    getattr(form, field_name).data = member.member_id
        
        return render_template('admin/edit_event_team.html', 
                             form=form, 
                             team=team,
                             event=team.event,
                             title=f"Edit {team.team_name}")
        
    except Exception as e:
        current_app.logger.error(f"Error in edit_event_team: {str(e)}")
        current_app.logger.error(f"Full traceback: ", exc_info=True)
        flash('An error occurred while editing the team.', 'error')
        # Try to get event_id from team if possible
        try:
            team = db.session.get(EventTeam, team_id)
            if team:
                return redirect(url_for('admin.manage_events', event_id=team.event_id, stage=3))
        except:
            pass
        return redirect(url_for('admin.manage_events'))


@bp.route('/add_event_team/<int:event_id>', methods=['GET', 'POST'])
@login_required
@role_required('Event Manager')
def add_event_team(event_id):
    """
    Admin interface for adding a new team to an event
    """
    try:
        from app.models import EventTeam
        from app.forms import AddTeamForm
        
        event = db.session.get(Event, event_id)
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check if user has permission to manage this event
        if not current_user.is_admin and current_user not in event.event_managers:
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Non-authorized user attempted to add team to event {event_id}')
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        form = AddTeamForm()
        
        if form.validate_on_submit():
            # Get the next team number
            existing_teams = db.session.scalars(
                sa.select(EventTeam).where(EventTeam.event_id == event_id)
            ).all()
            next_team_number = len(existing_teams) + 1
            
            # Create the new team
            new_team = EventTeam(
                event_id=event_id,
                team_name=form.team_name.data,
                team_number=next_team_number
            )
            db.session.add(new_team)
            db.session.commit()
            
            # Audit log the team creation
            audit_log_create('EventTeam', new_team.id, 
                            f'Created team: {new_team.team_name} for event "{event.name}"',
                            {'team_number': next_team_number})
            
            flash(f'Team "{new_team.team_name}" added successfully!', 'success')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        return render_template('admin/add_event_team.html', 
                             form=form, 
                             event=event,
                             title=f"Add Team to {event.name}")
        
    except Exception as e:
        current_app.logger.error(f"Error in add_event_team: {str(e)}")
        flash('An error occurred while adding the team.', 'error')
        return redirect(url_for('admin.manage_events', event_id=event_id))


@bp.route('/delete_event_team/<int:team_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def delete_event_team(team_id):
    """
    Admin interface for deleting an event team
    """
    try:
        from app.models import EventTeam
        
        # Get team first to get event_id for redirects
        team = db.session.get(EventTeam, team_id)
        if not team:
            flash('Team not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        event_id = team.event_id
        team_name = team.team_name
        
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Check if user has permission to manage this event
        if not current_user.is_admin and current_user not in team.event.event_managers:
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Non-authorized user attempted to delete team {team_id}')
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        event_name = team.event.name
        
        # Check if this team has associated booking teams
        booking_teams_count = len(team.booking_teams)
        if booking_teams_count > 0:
            # Get unique bookings that use this team
            affected_bookings = list(set([bt.booking for bt in team.booking_teams]))
            booking_dates = [booking.booking_date.strftime('%Y-%m-%d') for booking in affected_bookings]
            
            flash(f'Warning: Team "{team_name}" is used in {booking_teams_count} booking(s) on {", ".join(booking_dates)}. '
                  f'Deleting this team will not affect existing bookings (they remain independent), '
                  f'but you won\'t be able to trace them back to this template.', 'warning')
        
        # Note: Pool registration status no longer tracked - members remain available for other bookings
        
        # Delete the team (cascade will handle team_members and booking_teams relationship)
        db.session.delete(team)
        db.session.commit()
        
        # Audit log the team deletion
        audit_log_delete('EventTeam', team_id, 
                        f'Deleted team: {team_name} from event "{event_name}"',
                        {'booking_teams_affected': booking_teams_count})
        
        if booking_teams_count > 0:
            flash(f'Team "{team_name}" deleted. Existing bookings remain unchanged.', 'info')
        else:
            flash(f'Team "{team_name}" deleted successfully!', 'success')
        
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        current_app.logger.error(f"Error in delete_event_team: {str(e)}")
        flash('An error occurred while deleting the team.', 'error')
        # Try to get event_id from team if possible, otherwise redirect without it
        try:
            team = db.session.get(EventTeam, team_id)
            if team:
                return redirect(url_for('admin.manage_events', event_id=team.event_id))
        except:
            pass
        return redirect(url_for('admin.manage_events'))


@bp.route('/create_teams_from_pool/<int:event_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def create_teams_from_pool(event_id):
    """
    Create teams from pool members with 'available' status
    """
    try:
        from app.models import EventTeam, TeamMember
        from app.audit import audit_log_create, audit_log_bulk_operation
        
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        event = db.session.get(Event, event_id)
        if not event or not event.has_pool_enabled():
            flash('Event not found or pool not enabled.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check if user has permission
        if not current_user.is_admin and current_user not in event.event_managers:
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Get registered pool members (available for team selection)
        available_members = event.pool.get_registered_members()
        if not available_members:
            flash('No available members in the pool to create teams.', 'warning')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Get team configuration from app config
        team_positions = current_app.config.get('TEAM_POSITIONS', {})
        positions = team_positions.get(event.format, [])
        
        if not positions:
            flash(f'No team positions configured for format: {event.format}', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        team_size = len(positions)
        num_complete_teams = len(available_members) // team_size
        
        if num_complete_teams == 0:
            flash(f'Not enough registered members ({len(available_members)}) to create a complete team (need {team_size}).', 'warning')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Get existing team count for numbering
        existing_teams_count = db.session.scalar(
            sa.select(sa.func.count(EventTeam.id)).where(EventTeam.event_id == event_id)
        ) or 0
        
        teams_created = 0
        members_assigned = 0
        
        # Create teams
        for team_num in range(num_complete_teams):
            team_number = existing_teams_count + team_num + 1
            team_name = f"Team {team_number}"
            
            # Create the team
            new_team = EventTeam(
                event_id=event_id,
                team_name=team_name,
                team_number=team_number
            )
            db.session.add(new_team)
            db.session.flush()  # Get team ID
            
            # Assign members to positions
            team_members_info = []
            for i, position in enumerate(positions):
                member_idx = (team_num * team_size) + i
                if member_idx < len(available_members):
                    member = available_members[member_idx]
                    
                    # Create team member assignment
                    team_member = TeamMember(
                        event_team_id=new_team.id,
                        member_id=member.id,
                        position=position
                    )
                    db.session.add(team_member)
                    
                    # Pool members remain available for multiple bookings - no status change needed
                    
                    team_members_info.append(f"{member.firstname} {member.lastname} ({position})")
                    members_assigned += 1
            
            teams_created += 1
            
            # Audit log each team creation
            audit_log_create('EventTeam', new_team.id, 
                            f'Created team from pool: {team_name} for event "{event.name}"',
                            {'members': team_members_info, 'created_from_pool': True})
        
        # Commit all changes
        db.session.commit()
        
        # Audit log bulk operation
        audit_log_bulk_operation('TEAM_CREATION_FROM_POOL', 'EventTeam', teams_created,
                                f'Created {teams_created} teams from pool for event "{event.name}"',
                                {'members_assigned': members_assigned, 'event_id': event_id})
        
        remaining_members = len(available_members) - members_assigned
        message = f'Successfully created {teams_created} teams with {members_assigned} members assigned.'
        if remaining_members > 0:
            message += f' {remaining_members} members remain available in the pool.'
        
        flash(message, 'success')
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating teams from pool: {str(e)}")
        flash('An error occurred while creating teams from the pool.', 'error')
        return redirect(url_for('admin.manage_events'))



@bp.route('/copy_teams_to_booking/<int:event_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def copy_teams_to_booking(event_id):
    """
    Create a booking from event teams (Stage 5: Booking system redesign)
    """
    try:
        from app.models import EventTeam, BookingTeam, BookingTeamMember, Booking
        from app.forms import BookingForm
        from app.audit import audit_log_create, audit_log_bulk_operation
        import json
        
        # Get form data
        booking_date = request.form.get('booking_date')
        session = request.form.get('session', type=int)
        vs = request.form.get('vs', '')
        home_away = request.form.get('home_away', 'home')
        priority = request.form.get('priority', '')
        
        if not booking_date or not session:
            flash('Booking date and session are required.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Parse date
        from datetime import datetime
        try:
            booking_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        event = db.session.get(Event, event_id)
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Check if user has permission
        if not current_user.is_admin and current_user not in event.event_managers:
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('admin.manage_events'))
        
        # Get event teams
        event_teams = db.session.scalars(
            sa.select(EventTeam).where(EventTeam.event_id == event_id)
            .order_by(EventTeam.team_number)
        ).all()
        
        if not event_teams:
            flash('No teams found for this event.', 'warning')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Create the booking
        new_booking = Booking(
            booking_date=booking_date,
            session=session,
            organizer_id=current_user.id,
            rink_count=len(event_teams),  # One rink per team
            booking_type='event',
            priority=priority,
            vs=vs,
            home_away=home_away,
            event_id=event_id
        )
        
        db.session.add(new_booking)
        db.session.flush()  # Get booking ID
        
        teams_copied = 0
        members_copied = 0
        
        # Copy each event team to booking team
        for event_team in event_teams:
            # Create booking team
            booking_team = BookingTeam(
                booking_id=new_booking.id,
                event_team_id=event_team.id,
                team_name=event_team.team_name,
                team_number=event_team.team_number
            )
            db.session.add(booking_team)
            db.session.flush()  # Get booking team ID
            
            # Copy team members
            for team_member in event_team.team_members:
                booking_team_member = BookingTeamMember(
                    booking_team_id=booking_team.id,
                    member_id=team_member.member_id,
                    position=team_member.position,
                    is_substitute=False,
                    availability_status='pending'
                )
                db.session.add(booking_team_member)
                members_copied += 1
            
            teams_copied += 1
        
        # Commit all changes
        db.session.commit()
        
        # Audit logging
        audit_log_create('Booking', new_booking.id, 
                        f'Created booking from event teams for {event.name} on {booking_date}',
                        {'teams_copied': teams_copied, 'members_copied': members_copied, 
                         'vs': vs, 'home_away': home_away})
        
        audit_log_bulk_operation('TEAM_TO_BOOKING_COPY', 'BookingTeam', teams_copied,
                                f'Copied {teams_copied} teams to booking for {event.name}',
                                {'booking_id': new_booking.id, 'event_id': event_id})
        
        flash(f'Successfully created booking with {teams_copied} teams and {members_copied} members.', 'success')
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error copying teams to booking: {str(e)}")
        flash('An error occurred while creating the booking.', 'error')
        return redirect(url_for('admin.manage_events'))


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
        
        # Check permission
        if not current_user.is_admin and current_user not in event.event_managers:
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
            return redirect(url_for('main.bookings'))
        
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
                return redirect(url_for('admin.manage_teams', booking_id=booking_id))
            
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
            
            return redirect(url_for('admin.manage_teams', booking_id=booking_id))
        
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
        return redirect(url_for('main.bookings'))


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
        
        # Check permission
        if not current_user.is_admin and current_user not in event.event_managers:
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