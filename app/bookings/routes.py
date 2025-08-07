"""
Booking management routes and functionality.
All booking-related routes migrated from main, admin, and api blueprints.
"""

from datetime import date, datetime, timedelta
import sqlalchemy as sa
from flask import render_template, flash, redirect, url_for, request, current_app, jsonify, abort
from flask_login import login_required, current_user
from flask_wtf import FlaskForm

from app import db
from app.bookings import bp
from app.models import Booking, Member, Team
from app.routes import role_required
from app.bookings.utils import add_home_games_filter
from app.bookings.utils import can_user_manage_event
from app.audit import audit_log_create, audit_log_update, audit_log_delete, audit_log_bulk_operation, audit_log_security_event, get_model_changes


@bp.route('/')
@login_required
def bookings():
    """
    Display bookings calendar/table view
    """
    try:
        # Get today's date for initial display
        today = date.today()
        
        # Get session configuration
        sessions = current_app.config.get('DAILY_SESSIONS', {})
        rinks = current_app.config.get('RINKS', 6)
        locale = current_app.config.get('LOCALE', 'en-GB')
        
        return render_template('booking_table.html', 
                             today=today.isoformat(),
                             sessions=sessions,
                             rinks=rinks,
                             locale=locale)
    except Exception as e:
        current_app.logger.error(f"Error in bookings route: {str(e)}")
        flash('An error occurred while loading the bookings page.', 'error')
        return render_template('booking_table.html', 
                             today=date.today().isoformat(),
                             sessions={},
                             rinks=6,
                             locale=current_app.config.get('LOCALE', 'en-GB'))


@bp.route('/get_bookings/<string:selected_date>')
@login_required
def get_bookings(selected_date):
    """
    Get bookings for a specific date (AJAX endpoint)
    """
    try:
        # Parse the selected date
        booking_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        
        # Get all bookings for this date
        bookings = db.session.scalars(
            sa.select(Booking)
            .where(Booking.booking_date == booking_date)
            .order_by(Booking.session)
        ).all()
        
        # Format bookings for JSON response
        bookings_data = []
        for booking in bookings:
            booking_info = {
                'id': booking.id,
                'session': booking.session,
                'rink_count': booking.rink_count,
                'booking_type': booking.booking_type,
                'organizer': f"{booking.organizer.firstname} {booking.organizer.lastname}",
                'organizer_notes': booking.organizer_notes
            }
            
            if booking.event:
                booking_info['event_name'] = booking.event.name
                booking_info['event_type'] = booking.event.event_type
                booking_info['vs'] = booking.vs
            
            bookings_data.append(booking_info)
        
        return jsonify({
            'success': True,
            'bookings': bookings_data,
            'date': selected_date,
            'total_rinks': current_app.config.get('RINKS', 6)
        })
    except Exception as e:
        current_app.logger.error(f"Error getting bookings for {selected_date}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/get_bookings_range/<string:start_date>/<string:end_date>')
@login_required
def get_bookings_range(start_date, end_date):
    """
    Get bookings for a date range (AJAX endpoint)
    """
    try:
        # Parse dates
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Get all bookings in the range
        bookings = db.session.scalars(
            sa.select(Booking)
            .where(
                Booking.booking_date >= start_date_obj,
                Booking.booking_date <= end_date_obj
            )
            .order_by(Booking.booking_date, Booking.session)
        ).all()
        
        # Organize bookings by date and session
        bookings_by_date = {}
        for booking in bookings:
            date_str = booking.booking_date.isoformat()
            if date_str not in bookings_by_date:
                bookings_by_date[date_str] = {}
            
            session = booking.session
            if session not in bookings_by_date[date_str]:
                bookings_by_date[date_str][session] = []
            
            # Safely get organizer name
            try:
                organizer_name = f"{booking.organizer.firstname} {booking.organizer.lastname}" if booking.organizer else "Unknown"
            except Exception as organizer_error:
                current_app.logger.error(f"Error accessing organizer for booking {booking.id}: {str(organizer_error)}")
                organizer_name = "Unknown"
            
            booking_info = {
                'id': booking.id,
                'rink_count': booking.rink_count,
                'booking_type': booking.booking_type,
                'organizer': organizer_name,
                'organizer_notes': booking.organizer_notes
            }
            
            if booking.booking_type == 'rollup':
                # For roll-ups, include player count from team members
                team_member_count = 0
                try:
                    if hasattr(booking, 'teams') and booking.teams:
                        for team in booking.teams:
                            if hasattr(team, 'members') and team.members:
                                team_member_count += len(team.members)
                except Exception as team_error:
                    current_app.logger.error(f"Error counting team members for booking {booking.id}: {str(team_error)}")
                    team_member_count = 0
                booking_info['player_count'] = team_member_count
            else:
                # For regular events, include event details from booking (booking IS the event now)
                booking_info['event_name'] = booking.name
                booking_info['event_type'] = booking.event_type
                booking_info['vs'] = booking.vs
                booking_info['home_away'] = booking.home_away
            
            bookings_by_date[date_str][session].append(booking_info)
        
        return jsonify({
            'success': True,
            'bookings': bookings_by_date,
            'rinks': current_app.config.get('RINKS', 6),
            'sessions': current_app.config.get('DAILY_SESSIONS', {}),
            'event_types': current_app.config.get('EVENT_TYPES', {})
        })
    except Exception as e:
        current_app.logger.error(f"Error getting bookings range {start_date} to {end_date}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# MOVED TO ROLLUPS BLUEPRINT: rollup functionality has been moved to the rollups blueprint
# - Book rollup: /rollups/book
# - Manage rollup: /rollups/manage/<id>
# - Respond to rollup: /rollups/respond/<id>/<action>
# - Cancel rollup: /rollups/cancel/<id>
# - Add/remove players: /rollups/add_player/<id>, /rollups/remove_player/<id>


@bp.route('/my_games', methods=['GET', 'POST'])
@login_required
def my_games():
    """
    Display user's upcoming games and allow availability confirmation
    """
    try:
        # Handle POST requests for availability confirmation
        if request.method == 'POST':
            csrf_form = FlaskForm()
            
            if csrf_form.validate_on_submit():
                assignment_id = request.form.get('assignment_id')
                action = request.form.get('action')
                
                if assignment_id and action:
                    from app.models import TeamMember
                    from app.audit import audit_log_update
                    
                    assignment = db.session.get(TeamMember, assignment_id)
                    if assignment and assignment.member_id == current_user.id:
                        if action == 'confirm_available':
                            assignment.availability_status = 'available'
                            assignment.confirmed_at = datetime.utcnow()
                            flash('Availability confirmed successfully!', 'success')
                        elif action == 'confirm_unavailable':
                            assignment.availability_status = 'unavailable'
                            assignment.confirmed_at = datetime.utcnow()
                            flash('Unavailability confirmed.', 'info')
                        
                        db.session.commit()
                        audit_log_update('TeamMember', assignment.id, 
                                       f'Updated availability status to {assignment.availability_status}')
                    else:
                        flash('Invalid assignment or unauthorized access.', 'error')
                else:
                    flash('Missing required information.', 'error')
            else:
                flash('Security validation failed. Please try again.', 'error')
            
            return redirect(url_for('bookings.my_games'))
        
        # GET request - display games
        from app.models import TeamMember, Team, Pool, PoolRegistration
        
        # Get current date
        today = date.today()
        
        # Get team assignments for current user (excluding rollups to avoid duplication)
        assignments = db.session.scalars(
            sa.select(TeamMember)
            .join(TeamMember.team)
            .join(Team.booking)
            .where(
                TeamMember.member_id == current_user.id,
                Team.booking_id.isnot(None),  # Only teams with bookings
                Booking.booking_type != 'rollup'  # Exclude rollups from regular assignments
            )
            .order_by(Booking.booking_date)
        ).all()
        
        # Get roll-up invitations for current user via team memberships
        roll_up_invitations = db.session.scalars(
            sa.select(TeamMember)
            .join(TeamMember.team)
            .join(Team.booking)
            .where(
                TeamMember.member_id == current_user.id,
                Team.booking_id.isnot(None),  # Only teams with bookings
                Booking.booking_type == 'rollup'
            )
            .order_by(Booking.booking_date)
        ).all()
        
        # Get pool registrations for current user (events they registered interest in)
        # Exclude pool registrations where user has already been assigned to a team for that booking
        assigned_booking_ids = {assignment.team.booking_id for assignment in assignments}
        assigned_booking_ids.update({invitation.team.booking_id for invitation in roll_up_invitations})
        
        current_app.logger.info(f"User {current_user.id} has team assignments for bookings: {assigned_booking_ids}")
        
        # Only show pool registrations for bookings where user is NOT already in a team
        if assigned_booking_ids:
            pool_registrations = db.session.scalars(
                sa.select(PoolRegistration)
                .join(PoolRegistration.pool)
                .join(Pool.booking)
                .where(
                    PoolRegistration.member_id == current_user.id,
                    PoolRegistration.status == 'registered',
                    ~Pool.booking_id.in_(assigned_booking_ids)  # Exclude bookings where user is already assigned to a team
                )
                .order_by(Booking.booking_date)
            ).all()
        else:
            # No team assignments, show all pool registrations
            pool_registrations = db.session.scalars(
                sa.select(PoolRegistration)
                .join(PoolRegistration.pool)
                .join(Pool.booking)
                .where(
                    PoolRegistration.member_id == current_user.id,
                    PoolRegistration.status == 'registered'
                )
                .order_by(Booking.booking_date)
            ).all()
        
        current_app.logger.info(f"User {current_user.id} has {len(pool_registrations)} pool registrations after filtering")
        
        # Create CSRF form for POST actions
        csrf_form = FlaskForm()
        
        return render_template('my_games.html', 
                             assignments=assignments,
                             roll_up_invitations=roll_up_invitations,
                             pool_registrations=pool_registrations,
                             today=today,
                             csrf_form=csrf_form)
                             
    except Exception as e:
        current_app.logger.error(f"Error in my_games route: {str(e)}")
        flash('An error occurred while loading your games.', 'error')
        return render_template('my_games.html', 
                             assignments=[], 
                             roll_up_invitations=[],
                             pool_registrations=[],
                             today=date.today(),
                             csrf_form=FlaskForm())


@bp.route('/admin/edit/<int:booking_id>', methods=['GET', 'POST'])
@login_required
@role_required('Event Manager')
def admin_edit_booking(booking_id):
    """
    Admin interface for editing existing bookings
    """
    try:
        from app.bookings.forms import BookingForm
        
        booking = db.session.get(Booking, booking_id)
        if not booking:
            flash('Booking not found.', 'error')
            return redirect(url_for('bookings.admin_list_bookings'))
        
        # Check permissions - must be able to manage the booking
        from app.bookings.utils import can_user_manage_booking
        if not can_user_manage_booking(current_user, booking):
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to edit booking {booking_id}')
            flash('You do not have permission to manage this booking.', 'error')
            return redirect(url_for('bookings.admin_list_bookings'))
        
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
                return redirect(url_for('bookings.admin_list_bookings'))
            else:
                return redirect(url_for('bookings.bookings'))
        
        # Get teams for this booking
        teams = db.session.scalars(
            sa.select(Team).where(Team.booking_id == booking_id)
        ).all()
        
        # Create team form for adding new teams
        from app.teams.forms import TeamForm
        team_form = TeamForm()
        
        # Debug logging
        current_app.logger.info(f"Rendering booking edit page for booking {booking_id}, found {len(teams)} teams")
        
        try:
            return render_template('admin_booking_form.html', 
                                 form=form, 
                                 booking=booking,
                                 teams=teams,
                                 team_form=team_form,
                                 title=f"Edit Booking #{booking.id}")
        except Exception as template_error:
            current_app.logger.error(f"Template rendering error: {str(template_error)}")
            # Try rendering without teams section
            return render_template('admin_booking_form.html', 
                                 form=form, 
                                 booking=booking,
                                 teams=[],
                                 team_form=team_form,
                                 title=f"Edit Booking #{booking.id}")
        
    except Exception as e:
        current_app.logger.error(f"Error in edit_booking: {str(e)}")
        flash('An error occurred while editing the booking.', 'error')
        return redirect(url_for('bookings.admin_list_bookings'))


# DELETED: admin_copy_teams_to_booking - EventTeam functionality has been removed
# Teams are now managed independently in the teams blueprint


# MOVED TO TEAMS BLUEPRINT: team management functionality has been moved to the teams blueprint
# - Manage teams: /teams/manage/<team_id>
# - Add substitute: /teams/add_substitute/<team_id>
# - Update availability: /teams/update_member_availability/<member_id>


@bp.route('/api/v1/booking/<int:booking_id>', methods=['GET'])
@login_required
def api_get_booking(booking_id):
    """
    Get booking details (AJAX endpoint)
    """
    try:
        booking = db.session.get(Booking, booking_id)
        if not booking:
            return jsonify({
                'success': False,
                'error': 'Booking not found'
            }), 404
        
        # Format booking data
        booking_data = {
            'id': booking.id,
            'booking_date': booking.booking_date.isoformat(),
            'session': booking.session,
            'rink_count': booking.rink_count,
            'booking_type': booking.booking_type,
            'organizer_name': f"{booking.organizer.firstname} {booking.organizer.lastname}" if booking.organizer else "Unknown",
            'organizer_notes': booking.organizer_notes,
            'vs': booking.vs,
            'home_away': booking.home_away,
            'priority': booking.priority
        }
        
        # Add event details if it's an event booking
        if booking.event:
            booking_data['event_id'] = booking.event.id
            booking_data['event_name'] = booking.event.name
            booking_data['event_type'] = booking.event.event_type
        
        # Add team details if they exist
        if booking.booking_type == 'event' and booking.teams:
            teams = []
            for team in booking.teams:
                team_data = {
                    'id': team.id,
                    'team_name': team.team_name,
                    'members': []
                }
                
                for member in team.members:
                    member_data = {
                        'id': member.id,
                        'name': f"{member.member.firstname} {member.member.lastname}",
                        'position': member.position,
                        'is_substitute': member.is_substitute,
                        'availability_status': member.availability_status
                    }
                    team_data['members'].append(member_data)
                
                teams.append(team_data)
            
            booking_data['teams'] = teams
        
        # Add roll-up player details if it's a roll-up
        elif booking.booking_type == 'rollup' and booking.teams:
            players = []
            for team in booking.teams:
                for member in team.members:
                    player_data = {
                        'id': member.id,
                        'name': f"{member.member.firstname} {member.member.lastname}",
                        'status': member.availability_status,
                        'response_at': member.confirmed_at.isoformat() if member.confirmed_at else None
                    }
                    players.append(player_data)
            
            booking_data['players'] = players
        
        return jsonify({
            'success': True,
            'booking': booking_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting booking {booking_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/v1/booking/<int:booking_id>', methods=['PUT'])
@login_required
@role_required('Event Manager')
def api_update_booking(booking_id):
    """
    Update booking details via API
    """
    try:
        from app.audit import audit_log_update, get_model_changes
        
        booking = db.session.get(Booking, booking_id)
        if not booking:
            return jsonify({
                'success': False,
                'error': 'Booking not found'
            }), 404
        
        # Check permissions - must be able to manage the associated event
        if booking.event and not can_user_manage_event(current_user, booking.event):
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized API attempt to update booking {booking_id} for event {booking.event.id}')
            return jsonify({
                'success': False,
                'error': 'Permission denied'
            }), 403
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Track changes for audit
        changes = {}
        
        # Update allowed fields
        if 'rink_count' in data:
            if not isinstance(data['rink_count'], int) or data['rink_count'] < 1:
                return jsonify({
                    'success': False,
                    'error': 'Invalid rink count'
                }), 400
            changes['rink_count'] = {'old': booking.rink_count, 'new': data['rink_count']}
            booking.rink_count = data['rink_count']
        
        if 'priority' in data:
            changes['priority'] = {'old': booking.priority, 'new': data['priority']}
            booking.priority = data['priority']
        
        if 'vs' in data:
            changes['vs'] = {'old': booking.vs, 'new': data['vs']}
            booking.vs = data['vs']
        
        if 'organizer_notes' in data:
            changes['organizer_notes'] = {'old': booking.organizer_notes, 'new': data['organizer_notes']}
            booking.organizer_notes = data['organizer_notes']
        
        db.session.commit()
        
        # Audit log
        audit_log_update('Booking', booking.id, f'Updated booking via API', changes)
        
        return jsonify({
            'success': True,
            'message': 'Booking updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating booking {booking_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/v1/booking/<int:booking_id>', methods=['DELETE'])
@login_required
@role_required('Event Manager')
def api_delete_booking(booking_id):
    """
    Delete booking via API
    """
    try:
        from app.audit import audit_log_delete
        
        booking = db.session.get(Booking, booking_id)
        if not booking:
            return jsonify({
                'success': False,
                'error': 'Booking not found'
            }), 404
        
        # Check permissions - must be able to manage the associated event
        if booking.event and not can_user_manage_event(current_user, booking.event):
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized API attempt to delete booking {booking_id} for event {booking.event.id}')
            return jsonify({
                'success': False,
                'error': 'Permission denied'
            }), 403
        
        booking_description = f"Booking #{booking.id} on {booking.booking_date}"
        
        # Delete booking (cascades to teams and players)
        db.session.delete(booking)
        db.session.commit()
        
        # Audit log
        audit_log_delete('Booking', booking_id, f'Deleted {booking_description}')
        
        return jsonify({
            'success': True,
            'message': 'Booking deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting booking {booking_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Admin team management routes (migrated from admin blueprint)

@bp.route('/admin/manage_teams/<int:booking_id>', methods=['GET', 'POST'])
@login_required
@role_required('Event Manager')
def admin_manage_teams(booking_id):
    """
    Admin interface for managing teams for a specific booking
    Accessible to admins and booking organizers
    """
    try:
        # Get the booking
        booking = db.session.get(Booking, booking_id)
        if not booking:
            flash('Booking not found.', 'error')
            return redirect(url_for('bookings.admin_list_bookings'))
        
        # Check if user has permission to manage teams
        if not current_user.is_admin and booking.organizer_id != current_user.id:
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to manage teams for booking {booking_id}')
            flash('You do not have permission to manage teams for this booking.', 'error')
            return redirect(url_for('bookings.bookings'))
        
        from app.models import Team, TeamMember
        
        # Get existing teams for this booking
        teams = db.session.scalars(
            sa.select(Team)
            .where(Team.booking_id == booking_id)
            .order_by(Team.team_name)
        ).all()
        
        # Auto-create teams if none exist - create one team per rink
        if not teams and request.method == 'GET':
            rink_count = booking.rink_count
            current_app.logger.info(f"Auto-creating {rink_count} teams for booking {booking_id} (rink count: {rink_count})")
            
            for i in range(1, rink_count + 1):
                team_name = f"Rink {i}"
                new_team = Team(
                    booking_id=booking_id,
                    team_name=team_name,
                    created_by=current_user.id
                )
                db.session.add(new_team)
            
            try:
                db.session.commit()
                
                # Audit log the auto-creation
                audit_log_bulk_operation('BULK_CREATE', 'Team', rink_count, 
                                       f'Auto-created {rink_count} teams for booking {booking_id} based on rink count')
                
                # Refresh teams list after creation
                teams = db.session.scalars(
                    sa.select(Team)
                    .where(Team.booking_id == booking_id)
                    .order_by(Team.team_name)
                ).all()
                
                flash(f'Automatically created {rink_count} teams based on rink count.', 'success')
                
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error auto-creating teams for booking {booking_id}: {str(e)}")
                flash('Error creating initial teams. You can add them manually.', 'error')
        
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
                    new_team = Team(
                        booking_id=booking_id,
                        team_name=team_name,
                        created_by=current_user.id
                    )
                    db.session.add(new_team)
                    db.session.commit()
                    
                    audit_log_create('Team', new_team.id, 
                                   f'Added team {team_name} to booking {booking_id}')
                    flash(f'Team "{team_name}" added successfully.', 'success')
                else:
                    flash('Team name is required.', 'error')
            
            elif action == 'add_player':
                team_id = request.form.get('team_id')
                member_id = request.form.get('member_id')
                position = request.form.get('position')
                
                if team_id and member_id and position:
                    team = db.session.get(Team, int(team_id))
                    member = db.session.get(Member, int(member_id))
                    
                    if team and member and team.booking_id == booking_id:
                        # Check if member is already in this team
                        existing = db.session.scalar(
                            sa.select(TeamMember).where(
                                TeamMember.team_id == team.id,
                                TeamMember.member_id == member.id
                            )
                        )
                        
                        if not existing:
                            team_member = TeamMember(
                                team_id=team.id,
                                member_id=member.id,
                                position=position,
                                availability_status='pending'
                            )
                            db.session.add(team_member)
                            db.session.commit()
                            
                            audit_log_create('TeamMember', team_member.id,
                                           f'Added {member.firstname} {member.lastname} to team {team.team_name} as {position}')
                            flash(f'{member.firstname} {member.lastname} added to {team.team_name} as {position}.', 'success')
                        else:
                            flash(f'{member.firstname} {member.lastname} is already in {team.team_name}.', 'error')
                    else:
                        flash('Invalid team or member selection.', 'error')
                else:
                    flash('Team, member, and position are required.', 'error')
            
            elif action == 'assign_player':
                # Handle drag-and-drop player assignment via AJAX
                team_id = request.form.get('team_id')
                member_id = request.form.get('member_id')
                position = request.form.get('position')
                from_team_id = request.form.get('from_team_id')
                
                try:
                    if team_id and member_id and position:
                        team = db.session.get(Team, int(team_id))
                        member = db.session.get(Member, int(member_id))
                        
                        if team and member and team.booking_id == booking_id:
                            # Check if team is finalized (locked)
                            if team.is_finalized():
                                return jsonify({'success': False, 'message': 'Team is finalized and cannot be modified'})
                            
                            # Check if position is already occupied
                            existing_in_position = db.session.scalar(
                                sa.select(TeamMember).where(
                                    TeamMember.team_id == team.id,
                                    TeamMember.position == position
                                )
                            )
                            
                            if existing_in_position:
                                return jsonify({'success': False, 'message': 'Position already occupied'})
                            
                            # If moving from another team, remove from there first
                            if from_team_id:
                                existing_assignment = db.session.scalar(
                                    sa.select(TeamMember).where(
                                        TeamMember.team_id == int(from_team_id),
                                        TeamMember.member_id == member.id
                                    )
                                )
                                if existing_assignment:
                                    db.session.delete(existing_assignment)
                            
                            # Check if member is already in this team (different position)
                            existing_in_team = db.session.scalar(
                                sa.select(TeamMember).where(
                                    TeamMember.team_id == team.id,
                                    TeamMember.member_id == member.id
                                )
                            )
                            
                            if existing_in_team:
                                # Update position
                                existing_in_team.position = position
                                db.session.commit()
                                
                                audit_log_update('TeamMember', existing_in_team.id,
                                               f'Updated {member.firstname} {member.lastname} position to {position} in team {team.team_name}')
                            else:
                                # Create new assignment
                                team_member = TeamMember(
                                    team_id=team.id,
                                    member_id=member.id,
                                    position=position,
                                    availability_status='pending'
                                )
                                db.session.add(team_member)
                                db.session.commit()
                                
                                audit_log_create('TeamMember', team_member.id,
                                               f'Assigned {member.firstname} {member.lastname} to team {team.team_name} as {position}')
                            
                            return jsonify({'success': True, 'message': 'Player assigned successfully'})
                        else:
                            return jsonify({'success': False, 'message': 'Invalid team or member'})
                    else:
                        return jsonify({'success': False, 'message': 'Missing required parameters'})
                        
                except Exception as e:
                    current_app.logger.error(f"Error assigning player: {str(e)}")
                    return jsonify({'success': False, 'message': 'Server error'})
            
            elif action == 'remove_player':
                # Handle player removal via AJAX
                team_member_id = request.form.get('team_member_id')
                
                try:
                    if team_member_id:
                        team_member = db.session.get(TeamMember, int(team_member_id))
                        
                        if team_member and team_member.team.booking_id == booking_id:
                            # Check if team is finalized (locked)
                            if team_member.team.is_finalized():
                                return jsonify({'success': False, 'message': 'Team is finalized and cannot be modified'})
                            
                            member_name = f"{team_member.member.firstname} {team_member.member.lastname}"
                            team_name = team_member.team.team_name
                            position = team_member.position
                            
                            db.session.delete(team_member)
                            db.session.commit()
                            
                            audit_log_delete('TeamMember', int(team_member_id),
                                           f'Removed {member_name} from {position} in team {team_name}')
                            
                            return jsonify({'success': True, 'message': 'Player removed successfully'})
                        else:
                            return jsonify({'success': False, 'message': 'Invalid team member'})
                    else:
                        return jsonify({'success': False, 'message': 'Team member ID required'})
                        
                except Exception as e:
                    current_app.logger.error(f"Error removing player: {str(e)}")
                    return jsonify({'success': False, 'message': 'Server error'})
            
            elif action == 'finalize_team':
                # Handle team finalization - lock team from changes
                team_id = request.form.get('team_id')
                
                if team_id:
                    team = db.session.get(Team, int(team_id))
                    
                    if team and team.booking_id == booking_id:
                        # Check if team is complete
                        team_positions = current_app.config.get('TEAM_POSITIONS', {})
                        required_positions = team_positions.get(booking.format, ['Player'])
                        
                        if len(team.members) == len(required_positions):
                            # Finalize the team (lock it)
                            if team.finalize_team():
                                db.session.commit()
                                
                                audit_log_update('Team', team.id,
                                               f'Finalized team {team.team_name} - locked from changes')
                                
                                flash(f'Team "{team.team_name}" has been finalized and locked! No further changes can be made.', 'success')
                            else:
                                flash(f'Team "{team.team_name}" is already finalized.', 'info')
                        else:
                            flash(f'Team "{team.team_name}" is not complete. Need {len(required_positions)} players but only has {len(team.members)}.', 'error')
                    else:
                        flash('Invalid team selection.', 'error')
                else:
                    flash('Team ID is required.', 'error')
            
            elif action == 'unfinalize_team':
                # Handle team unfinalizing - unlock team for changes
                team_id = request.form.get('team_id')
                
                if team_id:
                    team = db.session.get(Team, int(team_id))
                    
                    if team and team.booking_id == booking_id:
                        if team.unfinalize_team():
                            db.session.commit()
                            
                            audit_log_update('Team', team.id,
                                           f'Unfinalized team {team.team_name} - unlocked for changes')
                            
                            flash(f'Team "{team.team_name}" has been unlocked for changes.', 'success')
                        else:
                            flash(f'Team "{team.team_name}" is not finalized.', 'info')
                    else:
                        flash('Invalid team selection.', 'error')
                else:
                    flash('Team ID is required.', 'error')
            
            elif action == 'substitute_player':
                import json
                
                booking_team_member_id = request.form.get('booking_team_member_id')
                new_member_id = request.form.get('new_member_id')
                reason = request.form.get('reason', 'No reason provided')
                
                if booking_team_member_id and new_member_id:
                    booking_team_member = db.session.get(TeamMember, int(booking_team_member_id))
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
                        audit_log_update('TeamMember', booking_team_member.id, 
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
        
        # Get assigned member IDs for visual feedback
        assigned_member_ids = {member.member_id for team in teams for member in team.members}
        
        # Get available members for substitutions 
        available_members = []
        if booking.has_pool_enabled():
            # Get all pool members (show all so user can see everyone, even if assigned)
            from app.models import PoolRegistration
            available_members = db.session.scalars(
                sa.select(Member)
                .join(PoolRegistration, Member.id == PoolRegistration.member_id)
                .where(PoolRegistration.pool_id == booking.pool.id)
                .order_by(Member.firstname, Member.lastname)
            ).all()
        else:
            # Fallback: get active members not already in the booking teams
            available_members = db.session.scalars(
                sa.select(Member)
                .where(Member.status.in_(['Full', 'Social', 'Life']))
                .where(~Member.id.in_(assigned_member_ids))
                .order_by(Member.firstname, Member.lastname)
            ).all()
        
        # Get team positions based on booking format
        team_positions = current_app.config.get('TEAM_POSITIONS', {})
        positions = team_positions.get(booking.format, ['Player'])
        
        # Create CSRF form for template
        csrf_form = FlaskForm()
        
        return render_template('admin_manage_teams.html', 
                             booking=booking,
                             teams=teams,
                             session_name=session_name,
                             available_members=available_members,
                             assigned_member_ids=assigned_member_ids,
                             positions=positions,
                             csrf_form=csrf_form)
        
    except Exception as e:
        current_app.logger.error(f"Error managing teams for booking {booking_id}: {str(e)}")
        flash('An error occurred while managing teams.', 'error')
        return redirect(url_for('bookings.bookings'))


@bp.route('/admin/list')
@login_required
@role_required('Event Manager')
def admin_list_bookings():
    """
    List all bookings for Event Manager management (replaces events.list_events)
    """
    try:
        # Get filter parameters
        event_type_filter = request.args.get('type', type=int)
        
        # Get all bookings (events are now bookings) - closest events first
        query = sa.select(Booking).order_by(Booking.booking_date.asc())
        
        if event_type_filter:
            query = query.where(Booking.event_type == event_type_filter)
        
        bookings = db.session.scalars(query).all()
        
        # Get event type options for filter
        event_types = current_app.config.get('EVENT_TYPES', {})
        
        # Calculate statistics for each booking
        booking_stats = {}
        for booking in bookings:
            try:
                # Safely calculate team count
                try:
                    total_teams = len(booking.teams) if hasattr(booking, 'teams') and booking.teams else 0
                except:
                    total_teams = 0
                
                # Safely calculate pool statistics
                try:
                    pool_members = len(booking.pool.registrations) if booking.pool and hasattr(booking.pool, 'registrations') else 0
                except:
                    pool_members = 0
                
                booking_stats[booking.id] = {
                    'total_teams': total_teams,
                    'has_pool': booking.pool is not None,
                    'pool_members': pool_members,
                    'pool_selected': 0,  # Simplified for now
                    'pool_available': pool_members,
                }
            except Exception as stats_error:
                current_app.logger.error(f"Error calculating stats for booking {booking.id}: {str(stats_error)}")
                booking_stats[booking.id] = {
                    'total_teams': 0,
                    'has_pool': False,
                    'pool_members': 0,
                    'pool_selected': 0,
                    'pool_available': 0,
                }
        
        # Group bookings by type and series
        regular_bookings = []
        rollup_bookings = []
        series_groups = {}
        
        for booking in bookings:
            if booking.booking_type == 'rollup':
                rollup_bookings.append(booking)
            elif booking.series_id:
                series_name = booking.get_series_name()
                if series_name not in series_groups:
                    series_groups[series_name] = []
                series_groups[series_name].append(booking)
            else:
                regular_bookings.append(booking)
        
        return render_template('admin_list_bookings.html', 
                             regular_bookings=regular_bookings,
                             series_groups=series_groups,
                             rollup_bookings=rollup_bookings,
                             booking_stats=booking_stats,
                             event_types=event_types,
                             current_filter=event_type_filter)
        
    except Exception as e:
        current_app.logger.error(f"Error in admin list bookings: {str(e)}")
        flash('An error occurred while loading bookings.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/admin/create', methods=['GET', 'POST'])
@login_required
@role_required('Event Manager')
def admin_create_booking():
    """
    Create a new booking/event (replaces events.create_event)
    """
    try:
        from app.forms import EventForm
        from app.bookings.utils import create_booking_with_defaults
        
        form = EventForm()
        
        if form.validate_on_submit():
            # Create new booking (representing an event)
            booking = create_booking_with_defaults(
                name=form.name.data,
                event_type=form.event_type.data,
                gender=form.gender.data,
                format=form.format.data,
                scoring=form.scoring.data,
                organizer_id=current_user.id,
                has_pool=form.has_pool.data,
            )
            
            db.session.add(booking)
            db.session.flush()  # Get booking ID
            
            # Add current user as booking manager
            booking.booking_managers.append(current_user)
            
            # Create pool if requested
            if form.has_pool.data:
                from app.models import Pool
                pool = Pool(
                    booking_id=booking.id,
                    is_open=True,
                    max_players=None,
                    auto_close_date=None
                )
                db.session.add(pool)
            
            db.session.commit()
            
            # Audit log
            audit_log_create('Booking', booking.id, 
                           f'Created event booking: {booking.name}',
                           {
                               'event_type': booking.event_type,
                               'format': booking.format,
                               'gender': booking.gender,
                               'has_pool': form.has_pool.data
                           })
            
            flash(f'Event "{booking.name}" created successfully!', 'success')
            return redirect(url_for('bookings.admin_manage_booking', booking_id=booking.id))
        
        return render_template('admin_create_booking.html', form=form)
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating booking: {str(e)}")
        flash('An error occurred while creating the event.', 'error')
        return redirect(url_for('bookings.admin_list_bookings'))


@bp.route('/admin/manage/<int:booking_id>', methods=['GET', 'POST'])
@login_required
@role_required('Event Manager')
def admin_manage_booking(booking_id):
    """
    Consolidated booking/event management interface with series support
    Replaces both admin_edit_booking and old events.manage_event
    """
    try:
        from app.forms import BookingManagementForm
        from app.bookings.utils import can_user_manage_booking, create_booking_with_defaults
        
        
        booking = db.session.get(Booking, booking_id)
        if not booking:
            flash('Booking not found.', 'error')
            return redirect(url_for('bookings.admin_list_bookings'))
        
        # Check permissions
        if not can_user_manage_booking(current_user, booking):
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to manage booking {booking_id}')
            flash('You do not have permission to manage this booking.', 'error')
            return redirect(url_for('bookings.admin_list_bookings'))
        
        # Calculate statistics
        try:
            total_teams = len(booking.teams) if hasattr(booking, 'teams') and booking.teams else 0
        except:
            total_teams = 0
            
        try:
            pool_members = len(booking.pool.registrations) if booking.pool and hasattr(booking.pool, 'registrations') else 0
        except:
            pool_members = 0
            
        stats = {
            'total_teams': total_teams,
            'has_pool': booking.pool is not None,
            'pool_members': pool_members,
            'pool_selected': 0,  # Simplified for now
            'pool_available': pool_members,
        }
        
        # Create consolidated form with current booking data
        form = BookingManagementForm()
        
        # Populate existing series dropdown
        existing_series_query = db.session.scalars(
            sa.select(Booking)
            .where(Booking.series_id.isnot(None))
            .where(Booking.series_id != booking.series_id)  # Exclude current booking's series
        ).all()
        
        series_choices = [('', 'Select a series...')]
        existing_series_names = {}
        
        for series_booking in existing_series_query:
            if series_booking.series_id not in existing_series_names:
                series_name = series_booking.get_series_name()
                existing_series_names[series_booking.series_id] = series_name
                series_choices.append((series_booking.series_id, series_name))
        
        form.existing_series.choices = series_choices
        
        # Debug: Log what series were found
        current_app.logger.info(f"Populating series dropdown for booking {booking_id}")
        current_app.logger.info(f"Found {len(series_choices)-1} existing series: {series_choices}")
        if len(series_choices) == 1:
            current_app.logger.info("No existing series found - dropdown will only show 'Select a series...'")
        
        # Debug: Log current booking's series status
        current_app.logger.info(f"Current booking series_id: {booking.series_id}")
        if booking.series_id:
            current_app.logger.info(f"Current booking series name: {booking.get_series_name()}")
        
        if request.method == 'GET':
            # Populate form with current booking data
            form.name.data = booking.name
            form.event_type.data = booking.event_type
            form.gender.data = booking.gender
            form.format.data = booking.format
            form.scoring.data = booking.scoring
            form.has_pool.data = booking.pool is not None
            form.booking_date.data = booking.booking_date
            form.session.data = booking.session
            form.rink_count.data = booking.rink_count
            form.vs.data = booking.vs
            form.home_away.data = booking.home_away
            form.series_id.data = booking.series_id if hasattr(booking, 'series_id') else None
            form.create_series.data = booking.series_id is not None
            form.series_name.data = booking.get_series_name() if booking.series_id else None
        
        if request.method == 'POST':
            # Check if this is a duplicate action from the modal
            action = request.form.get('action')
            
            if action == 'duplicate':
                # Handle modal-based duplication
                try:
                    # Get duplicate parameters from the modal form
                    duplicate_date_str = request.form.get('duplicate_date')
                    duplicate_session = request.form.get('duplicate_session') 
                    duplicate_venue = request.form.get('duplicate_venue')
                    duplicate_opposition = request.form.get('duplicate_opposition')
                    
                    # Parse the date
                    from datetime import datetime
                    duplicate_date = datetime.strptime(duplicate_date_str, '%Y-%m-%d').date() if duplicate_date_str else None
                    
                    if not duplicate_date or not duplicate_session:
                        flash('Date and session are required for duplication.', 'error')
                        return render_template('admin_manage_booking.html', 
                                             booking=booking,
                                             form=form,
                                             stats=stats)
                    
                    # Create duplicate booking with modified fields
                    duplicate_booking = create_booking_with_defaults(
                        name=booking.name,  # Keep original name
                        event_type=booking.event_type,
                        gender=booking.gender,
                        format=booking.format,
                        scoring=booking.scoring or None,  # Handle empty scoring
                        booking_date=duplicate_date,  # Use new date
                        session=int(duplicate_session),  # Use new session
                        rink_count=booking.rink_count,
                        vs=duplicate_opposition if duplicate_opposition else booking.vs,  # Use new opposition or keep original
                        home_away=duplicate_venue if duplicate_venue else booking.home_away,  # Use new venue or keep original
                        organizer_id=booking.organizer_id,
                        has_pool=booking.has_pool,
                        series_id=booking.series_id if hasattr(booking, 'series_id') and booking.series_id else None
                    )
                    
                    # Add to database and commit
                    db.session.add(duplicate_booking)
                    db.session.commit()
                    
                    # Create pool based on EVENT_POOL_STRATEGY
                    from app.bookings.utils import should_create_pool_for_duplication
                    should_create, reason = should_create_pool_for_duplication(booking, duplicate_booking)
                    
                    if should_create:
                        from app.models import Pool
                        new_pool = Pool(booking_id=duplicate_booking.id, is_open=True)
                        if booking.pool:
                            new_pool.max_players = booking.pool.max_players
                        db.session.add(new_pool)
                        db.session.commit()
                        current_app.logger.info(f"Created new pool for duplicate booking {duplicate_booking.id}: {reason}")
                    else:
                        current_app.logger.info(f"No pool created for duplicate booking {duplicate_booking.id}: {reason}")
                    
                    # Audit log the duplication
                    from app.audit import audit_log_create
                    audit_log_create('Booking', duplicate_booking.id, 
                                   f'Duplicated booking: {duplicate_booking.name} for {duplicate_date}')
                    
                    flash(f'Successfully created duplicate event for {duplicate_date}!', 'success')
                    return redirect(url_for('bookings.admin_manage_booking', booking_id=duplicate_booking.id))
                        
                except Exception as e:
                    current_app.logger.error(f"Error creating duplicate booking: {str(e)}")
                    flash('An error occurred while creating the duplicate event.', 'error')
                
                # Return after handling duplicate to prevent further form processing
                return render_template('admin_manage_booking.html', 
                                     booking=booking,
                                     form=form,
                                     stats=stats)
                    
            # Debug: Log form submission details
            current_app.logger.info(f"POST request received for booking {booking_id}")
            current_app.logger.info(f"Form data - duplicate: {form.duplicate.data}")
            current_app.logger.info(f"Form data - submit: {form.submit.data}")
            current_app.logger.info(f"Form data - existing_series: '{form.existing_series.data}'")
            current_app.logger.info(f"Form data - series_id: '{form.series_id.data}'")
            current_app.logger.info(f"Form data - create_series: {form.create_series.data}")
            current_app.logger.info(f"Form data - has_pool: {form.has_pool.data}")
            
            if not form.validate_on_submit():
                current_app.logger.warning(f"Form validation failed: {form.errors}")
                flash('Form validation failed. Please check your inputs.', 'error')
            
            if form.validate_on_submit():
                # Check which button was clicked
                current_app.logger.info("Form validation passed - checking which button was clicked")
                try:
                    current_app.logger.info(f"About to check form.duplicate.data: {form.duplicate.data}")
                    if form.duplicate.data:
                        # Handle duplication/series creation
                        current_app.logger.info("Handling duplication")
                        duplicate_booking = create_booking_with_defaults(
                            name=form.name.data,
                            event_type=form.event_type.data,
                            gender=form.gender.data,
                            format=form.format.data,
                            scoring=form.scoring.data,
                            booking_date=form.booking_date.data,
                            session=form.session.data,
                            rink_count=form.rink_count.data,
                            vs=form.vs.data,
                            home_away=form.home_away.data,
                            organizer_id=booking.organizer_id,
                            has_pool=form.has_pool.data,
                            series_id=booking.series_id if hasattr(booking, 'series_id') else None
                        )
                        
                        # If creating a series, generate series_id if needed
                        if form.create_series.data and not duplicate_booking.series_id:
                            import uuid
                            series_id = str(uuid.uuid4())
                            # Update both original and duplicate with series_id
                            booking.series_id = series_id
                            duplicate_booking.series_id = series_id
                        
                        db.session.add(duplicate_booking)
                        db.session.commit()
                        
                        # Create pool for duplicate based on EVENT_POOL_STRATEGY
                        from app.bookings.utils import should_create_pool_for_duplication
                        should_create, reason = should_create_pool_for_duplication(booking, duplicate_booking)
                        
                        if should_create and form.has_pool.data:
                            from app.models import Pool
                            duplicate_pool = Pool(
                                booking_id=duplicate_booking.id,
                                is_open=True,
                                max_players=booking.pool.max_players if booking.pool else None
                            )
                            db.session.add(duplicate_pool)
                            db.session.commit()
                            current_app.logger.info(f"Created new pool for duplicate booking {duplicate_booking.id}: {reason}")
                        else:
                            current_app.logger.info(f"No pool created for duplicate booking {duplicate_booking.id}: {reason}")
                        
                        from app.audit import audit_log_create
                        audit_log_create('Booking', duplicate_booking.id, 
                                       f'Duplicated booking: {duplicate_booking.name} from booking {booking.id}')
                        
                        flash(f'Event duplicated successfully! New event created for {duplicate_booking.booking_date}', 'success')
                        return redirect(url_for('bookings.admin_manage_booking', booking_id=duplicate_booking.id))
                
                except Exception as e:
                    current_app.logger.error(f"Error in duplication handling: {str(e)}")
                    db.session.rollback()
                    flash('An error occurred while processing the form.', 'error')
                    
                else:
                    # Handle regular update
                    current_app.logger.info("Handling regular update (not duplicate)")
                    changes = {}
                
                    # Track all changes
                    if booking.name != form.name.data:
                        changes['name'] = {'old': booking.name, 'new': form.name.data}
                        booking.name = form.name.data
                        
                    if booking.event_type != form.event_type.data:
                        changes['event_type'] = {'old': booking.event_type, 'new': form.event_type.data}
                        booking.event_type = form.event_type.data
                        
                    if booking.gender != form.gender.data:
                        changes['gender'] = {'old': booking.gender, 'new': form.gender.data}
                        booking.gender = form.gender.data
                        
                    if booking.format != form.format.data:
                        changes['format'] = {'old': booking.format, 'new': form.format.data}
                        booking.format = form.format.data
                        
                    if booking.scoring != form.scoring.data:
                        changes['scoring'] = {'old': booking.scoring, 'new': form.scoring.data}
                        booking.scoring = form.scoring.data
                        
                    if booking.booking_date != form.booking_date.data:
                        changes['booking_date'] = {'old': booking.booking_date.isoformat(), 'new': form.booking_date.data.isoformat()}
                        booking.booking_date = form.booking_date.data
                    
                    if booking.session != form.session.data:
                        changes['session'] = {'old': booking.session, 'new': form.session.data}
                        booking.session = form.session.data
                        
                    if booking.rink_count != form.rink_count.data:
                        changes['rink_count'] = {'old': booking.rink_count, 'new': form.rink_count.data}
                        booking.rink_count = form.rink_count.data
                        
                    if booking.vs != form.vs.data:
                        changes['vs'] = {'old': booking.vs, 'new': form.vs.data}
                        booking.vs = form.vs.data
                        
                    if booking.home_away != form.home_away.data:
                        changes['home_away'] = {'old': booking.home_away, 'new': form.home_away.data}
                        booking.home_away = form.home_away.data
                    
                    # Handle series changes from existing_series dropdown
                    if form.existing_series.data and form.existing_series.data != booking.series_id:
                        current_app.logger.info(f"Series change detected: {booking.series_id} -> {form.existing_series.data}")
                        changes['series_id'] = {'old': booking.series_id, 'new': form.existing_series.data}
                        booking.series_id = form.existing_series.data
                        current_app.logger.info(f"Successfully updated booking {booking.id} series_id to {form.existing_series.data}")
                    
                    # Handle pool creation/deletion
                    current_has_pool = booking.pool is not None
                    current_app.logger.info(f"Pool status check - booking.id: {booking.id}, current_has_pool: {current_has_pool}, form.has_pool.data: {form.has_pool.data}")
                    
                    if current_has_pool != form.has_pool.data:
                        if form.has_pool.data and not current_has_pool:
                            # Create new pool
                            from app.models import Pool
                            new_pool = Pool(booking_id=booking.id, is_open=True)
                            db.session.add(new_pool)
                            booking.has_pool = True
                            changes['pool'] = {'old': 'None', 'new': 'Created'}
                            current_app.logger.info(f"Created new pool for booking {booking.id}")
                        elif not form.has_pool.data and current_has_pool:
                            # Delete existing pool
                            db.session.delete(booking.pool)
                            booking.has_pool = False
                            changes['pool'] = {'old': 'Exists', 'new': 'Deleted'}
                            current_app.logger.info(f"Deleted pool for booking {booking.id}")
                    
                    db.session.commit()
                    
                    # Verify pool creation after commit
                    db.session.refresh(booking)
                    pool_after_commit = booking.pool is not None
                    current_app.logger.info(f"After commit - booking.id: {booking.id}, pool exists: {pool_after_commit}, booking.has_pool: {booking.has_pool}")
                    
                    # Audit log changes
                    if changes:
                        from app.audit import audit_log_update
                        audit_log_update('Booking', booking.id, 
                                       f'Updated booking: {booking.name}', changes)
                    
                    flash('Event updated successfully!', 'success')
                    return redirect(url_for('bookings.admin_manage_booking', booking_id=booking_id))
        
        return render_template('admin_manage_booking.html', 
                             booking=booking,
                             form=form,
                             stats=stats)
                             
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"Error managing booking {booking_id}: {str(e)}")
        current_app.logger.error(f"Full traceback: {error_details}")
        flash(f'An error occurred while managing the booking: {str(e)}', 'error')
        return redirect(url_for('bookings.admin_list_bookings'))


@bp.route('/admin/delete/<int:booking_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def admin_delete_booking(booking_id):
    """
    Delete a booking/event (replaces events.delete_event)
    """
    try:
        from app.bookings.utils import can_user_manage_booking
        
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('bookings.admin_list_bookings'))
        
        booking = db.session.get(Booking, booking_id)
        if not booking:
            flash('Booking not found.', 'error')
            return redirect(url_for('bookings.admin_list_bookings'))
        
        # Check permissions
        if not can_user_manage_booking(current_user, booking):
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to delete booking {booking_id}')
            flash('You do not have permission to delete this booking.', 'error')
            return redirect(url_for('bookings.admin_list_bookings'))
        
        booking_name = booking.name
        event_type_name = booking.get_event_type_name()
        
        # Delete booking (cascades to pool and teams if they exist)
        db.session.delete(booking)
        db.session.commit()
        
        # Audit log
        audit_log_delete('Booking', booking_id, 
                        f'Deleted booking: {booking_name} ({event_type_name})')
        
        flash(f'Event "{booking_name}" deleted successfully.', 'success')
        return redirect(url_for('bookings.admin_list_bookings'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting booking {booking_id}: {str(e)}")
        flash('An error occurred while deleting the booking.', 'error')
        return redirect(url_for('bookings.admin_list_bookings'))