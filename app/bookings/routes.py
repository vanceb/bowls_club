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
from app.models import Booking, Member, Event
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
                # For roll-ups, include player count from team members
                team_member_count = 0
                if booking.teams:
                    for team in booking.teams:
                        team_member_count += len(team.members)
                booking_info['player_count'] = team_member_count
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
        from app.models import TeamMember, Team
        
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