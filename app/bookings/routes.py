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
from app.models import Booking, BookingPlayer, Member, BookingTeam, BookingTeamMember, Event, EventTeam, TeamMember
from app.routes import role_required
from app.bookings.utils import add_home_games_filter
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
        
        return render_template('booking_table.html', 
                             today=today.isoformat(),
                             sessions=sessions,
                             rinks=rinks)
    except Exception as e:
        current_app.logger.error(f"Error in bookings route: {str(e)}")
        flash('An error occurred while loading the bookings page.', 'error')
        return render_template('booking_table.html', 
                             today=date.today().isoformat(),
                             sessions={},
                             rinks=6)


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
            
            booking_info = {
                'id': booking.id,
                'rink_count': booking.rink_count,
                'booking_type': booking.booking_type,
                'organizer': f"{booking.organizer.firstname} {booking.organizer.lastname}" if booking.organizer else "Unknown",
                'organizer_notes': booking.organizer_notes
            }
            
            if booking.booking_type == 'rollup':
                # For roll-ups, include player count
                booking_info['player_count'] = len(booking.booking_players)
            elif booking.event:
                # For regular events, include event details
                booking_info['event_name'] = booking.event.name
                booking_info['event_type'] = booking.event.event_type
                booking_info['vs'] = booking.vs
            
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
                    from app.models import BookingTeamMember
                    from app.audit import audit_log_update
                    
                    assignment = db.session.get(BookingTeamMember, assignment_id)
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
                        audit_log_update('BookingTeamMember', assignment.id, 
                                       f'Updated availability status to {assignment.availability_status}')
                    else:
                        flash('Invalid assignment or unauthorized access.', 'error')
                else:
                    flash('Missing required information.', 'error')
            else:
                flash('Security validation failed. Please try again.', 'error')
            
            return redirect(url_for('bookings.my_games'))
        
        # GET request - display games
        from app.models import BookingTeamMember
        
        # Get current date
        today = date.today()
        
        # Get team assignments for current user
        from app.models import BookingTeam, Booking
        assignments = db.session.scalars(
            sa.select(BookingTeamMember)
            .join(BookingTeamMember.booking_team)
            .join(BookingTeam.booking)
            .where(BookingTeamMember.member_id == current_user.id)
            .order_by(Booking.booking_date)
        ).all()
        
        # Get roll-up invitations for current user (include organizer's own rollups)
        roll_up_invitations = db.session.scalars(
            sa.select(BookingPlayer)
            .join(BookingPlayer.booking)
            .where(BookingPlayer.member_id == current_user.id)
            .order_by(Booking.booking_date)
        ).all()
        
        # Create CSRF form for POST actions
        csrf_form = FlaskForm()
        
        return render_template('my_games.html', 
                             assignments=assignments,
                             roll_up_invitations=roll_up_invitations,
                             today=today,
                             csrf_form=csrf_form)
                             
    except Exception as e:
        current_app.logger.error(f"Error in my_games route: {str(e)}")
        flash('An error occurred while loading your games.', 'error')
        return render_template('my_games.html', 
                             assignments=[], 
                             roll_up_invitations=[],
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
                return redirect(url_for('bookings.bookings'))
        
        return render_template('admin_booking_form.html', 
                             form=form, 
                             booking=booking,
                             title=f"Edit Booking #{booking.id}")
        
    except Exception as e:
        current_app.logger.error(f"Error in edit_booking: {str(e)}")
        flash('An error occurred while editing the booking.', 'error')
        return redirect(url_for('admin.manage_events'))


@bp.route('/admin/copy_teams_to_booking/<int:event_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def admin_copy_teams_to_booking(event_id):
    """
    Create a booking from event teams (Stage 5: Booking system redesign)
    """
    try:
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
        ).all()
        
        if not event_teams:
            flash('No teams available to copy to booking.', 'error')
            return redirect(url_for('admin.manage_events', event_id=event_id))
        
        # Create the booking
        booking = Booking(
            event_id=event_id,
            booking_date=booking_date,
            session=session,
            rink_count=len(event_teams),
            booking_type='event',
            organizer_id=current_user.id,
            vs=vs,
            home_away=home_away,
            priority=priority
        )
        db.session.add(booking)
        db.session.flush()  # Get booking ID
        
        # Copy teams and members
        teams_copied = 0
        members_copied = 0
        
        for event_team in event_teams:
            # Create booking team
            booking_team = BookingTeam(
                booking_id=booking.id,
                team_name=event_team.team_name,
                event_team_id=event_team.id
            )
            db.session.add(booking_team)
            db.session.flush()  # Get team ID
            
            # Copy team members
            team_members = db.session.scalars(
                sa.select(TeamMember).where(TeamMember.event_team_id == event_team.id)
            ).all()
            
            for team_member in team_members:
                booking_team_member = BookingTeamMember(
                    booking_team_id=booking_team.id,
                    member_id=team_member.member_id,
                    position=team_member.position,
                    is_substitute=team_member.is_substitute,
                    availability_status='pending'
                )
                db.session.add(booking_team_member)
                members_copied += 1
            
            teams_copied += 1
        
        db.session.commit()
        
        # Audit logs
        audit_log_create('Booking', booking.id, 
                        f'Created booking from event {event.name} teams')
        audit_log_bulk_operation('BULK_CREATE', 'BookingTeam', teams_copied,
                               f'Copied {teams_copied} teams to booking {booking.id}')
        audit_log_bulk_operation('BULK_CREATE', 'BookingTeamMember', members_copied,
                               f'Copied {members_copied} members to booking {booking.id}')
        
        flash(f'Booking created successfully with {teams_copied} teams and {members_copied} members!', 'success')
        return redirect(url_for('admin.manage_events', event_id=event_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error copying teams to booking: {str(e)}")
        flash('An error occurred while creating the booking.', 'error')
        return redirect(url_for('admin.manage_events', event_id=event_id))


@bp.route('/admin/add_substitute_to_team/<int:booking_team_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def admin_add_substitute_to_team(booking_team_id):
    """
    Add a substitute to a booking team
    """
    try:
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
        
        # Get member for audit log
        member = db.session.get(Member, member_id)
        audit_log_create('BookingTeamMember', substitute.id, 
                        f'Added substitute {member.firstname} {member.lastname} to team {booking_team.team_name}')
        
        flash(f'Substitute {member.firstname} {member.lastname} added successfully.', 'success')
        return redirect(url_for('admin.manage_events', event_id=booking_team.booking.event_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding substitute: {str(e)}")
        flash('An error occurred while adding the substitute.', 'error')
        return redirect(url_for('admin.manage_events'))


@bp.route('/admin/update_member_availability/<int:booking_team_member_id>', methods=['POST'])
@login_required
def admin_update_member_availability(booking_team_member_id):
    """
    Update a team member's availability status (accessible to team members and admins)
    """
    try:
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
            return redirect(url_for('admin.manage_events'))
        
        # Check if user has permission to manage teams
        if not current_user.is_admin and booking.organizer_id != current_user.id:
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to manage teams for booking {booking_id}')
            flash('You do not have permission to manage teams for this booking.', 'error')
            return redirect(url_for('bookings.bookings'))
        
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
                                       f'Substituted {original_player_name} with {substitute_player_name} for position {position}',
                                       substitution_log_entry)
                        
                        flash(f'Successfully substituted {original_player_name} with {substitute_player_name}.', 'success')
                    else:
                        flash('Invalid player selection.', 'error')
                else:
                    flash('Player and substitute information required.', 'error')
            
            # Refresh teams data after changes
            teams = db.session.scalars(
                sa.select(BookingTeam)
                .where(BookingTeam.booking_id == booking_id)
                .order_by(BookingTeam.team_name)
            ).all()
        
        # Get available members for substitutions
        available_members = db.session.scalars(
            sa.select(Member)
            .where(Member.status.in_(['Full', 'Life', 'Social']))
            .order_by(Member.firstname, Member.lastname)
        ).all()
        
        # Create CSRF form for template
        csrf_form = FlaskForm()
        
        return render_template('admin_manage_teams.html',
                             booking=booking,
                             teams=teams,
                             available_members=available_members,
                             csrf_form=csrf_form)
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error managing teams for booking {booking_id}: {str(e)}")
        flash('An error occurred while managing teams.', 'error')
        return redirect(url_for('admin.manage_events'))


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
        if booking.booking_type == 'event' and booking.booking_teams:
            teams = []
            for team in booking.booking_teams:
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
        elif booking.booking_type == 'rollup' and booking.booking_players:
            players = []
            for player in booking.booking_players:
                player_data = {
                    'id': player.id,
                    'name': f"{player.member.firstname} {player.member.lastname}",
                    'status': player.status,
                    'response_at': player.response_at.isoformat() if player.response_at else None
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