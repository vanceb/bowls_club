from flask import render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import login_required, current_user
from datetime import date, datetime
import sqlalchemy as sa

from app.rollups import bp
from app import db
from app.models import Booking, Team, TeamMember, Member
from app.forms import FlaskForm
from app.audit import audit_log_create, audit_log_update, audit_log_delete


@bp.route('/book', methods=['GET', 'POST'])
@login_required
def book_rollup():
    """
    Create a roll-up booking and invite players
    """
    try:
        from app.rollups.forms import RollUpBookingForm
        
        form = RollUpBookingForm()
        
        if form.validate_on_submit():
            # Create the booking
            booking = Booking(
                booking_date=form.booking_date.data,
                session=form.session.data,
                organizer_id=current_user.id,
                rink_count=1,  # Roll-ups always use 1 rink
                booking_type='rollup',
                organizer_notes=form.organizer_notes.data
            )
            
            db.session.add(booking)
            db.session.flush()  # Get the booking ID
            
            # Create a team for this rollup
            rollup_team = Team(
                booking_id=booking.id,
                team_name=f"Roll-up {booking.booking_date}",
                created_by=current_user.id
            )
            db.session.add(rollup_team)
            db.session.flush()  # Get the team ID
            
            # Add organizer as confirmed team member
            organizer_member = TeamMember(
                team_id=rollup_team.id,
                member_id=current_user.id,
                position='Player',
                availability_status='available',  # Organizer is automatically available
                confirmed_at=datetime.utcnow()
            )
            db.session.add(organizer_member)
            
            # Add invited players as team members
            if form.invited_players.data:
                invited_player_ids = [int(x.strip()) for x in form.invited_players.data.split(',') if x.strip()]
                for player_id in invited_player_ids:
                    if player_id != current_user.id:  # Don't invite organizer again
                        invited_member = TeamMember(
                            team_id=rollup_team.id,
                            member_id=player_id,
                            position='Player',
                            availability_status='pending'
                        )
                        db.session.add(invited_member)
            
            db.session.commit()
            
            # Audit log
            audit_log_create('Booking', booking.id, 
                           f'Created roll-up booking for {booking.booking_date}')
            
            flash('Roll-up booking created successfully!', 'success')
            return redirect(url_for('bookings.my_games'))
        
        return render_template('book_rollup.html', form=form)
        
    except Exception as e:
        current_app.logger.error(f"Error in book_rollup route: {str(e)}")
        flash('An error occurred while booking the roll-up.', 'error')
        return redirect(url_for('bookings.my_games'))


@bp.route('/respond/<int:booking_id>/<action>')
@login_required
def respond_to_rollup(booking_id, action):
    """
    Respond to a roll-up invitation
    """
    try:
        # Get the booking
        booking = db.session.get(Booking, booking_id)
        if not booking or booking.booking_type != 'rollup':
            flash('Invalid roll-up booking.', 'error')
            return redirect(url_for('bookings.my_games'))
        
        # Get the team member invitation
        invitation = db.session.scalar(
            sa.select(TeamMember)
            .join(Team)
            .where(
                Team.booking_id == booking_id,
                TeamMember.member_id == current_user.id
            )
        )
        
        if not invitation:
            flash('You are not invited to this roll-up.', 'error')
            return redirect(url_for('bookings.my_games'))
        
        # Update the response
        if action == 'accept':
            invitation.availability_status = 'available'
            invitation.confirmed_at = datetime.utcnow()
            flash('Roll-up invitation accepted!', 'success')
        elif action == 'decline':
            invitation.availability_status = 'unavailable'
            invitation.confirmed_at = datetime.utcnow()
            flash('Roll-up invitation declined.', 'info')
        else:
            flash('Invalid action.', 'error')
            return redirect(url_for('bookings.my_games'))
        
        db.session.commit()
        
        # Audit log
        audit_log_update('TeamMember', invitation.id, 
                       f'Updated roll-up response to {invitation.availability_status}')
        
        return redirect(url_for('bookings.my_games'))
        
    except Exception as e:
        current_app.logger.error(f"Error responding to roll-up {booking_id}: {str(e)}")
        flash('An error occurred while responding to the roll-up.', 'error')
        return redirect(url_for('bookings.my_games'))


@bp.route('/manage/<int:booking_id>')
@login_required
def manage_rollup(booking_id):
    """
    Manage a roll-up booking (organizer only)
    """
    try:
        # Get the booking
        booking = db.session.get(Booking, booking_id)
        if not booking or booking.booking_type != 'rollup':
            abort(404)
        
        # Check if user is the organizer
        if booking.organizer_id != current_user.id:
            abort(403)
        
        # Get the rollup team for this booking
        rollup_team = db.session.scalar(
            sa.select(Team)
            .where(Team.booking_id == booking_id)
        )
        
        if not rollup_team:
            flash('Roll-up team not found.', 'error')
            return redirect(url_for('bookings.my_games'))
        
        # Redirect to team management page which handles all team functionality
        return redirect(url_for('teams.manage_team', team_id=rollup_team.id))
        
    except Exception as e:
        current_app.logger.error(f"Error managing roll-up {booking_id}: {str(e)}")
        flash('An error occurred while loading the roll-up management page.', 'error')
        return redirect(url_for('bookings.my_games'))


@bp.route('/cancel/<int:booking_id>', methods=['POST'])
@login_required
def cancel_rollup(booking_id):
    """
    Cancel a roll-up booking (organizer only)
    """
    try:
        # Validate CSRF
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('bookings.my_games'))
        
        # Get the booking
        booking = db.session.get(Booking, booking_id)
        if not booking or booking.booking_type != 'rollup':
            flash('Invalid roll-up booking.', 'error')
            return redirect(url_for('bookings.my_games'))
        
        # Check if user is the organizer
        if booking.organizer_id != current_user.id:
            flash('You are not authorized to cancel this roll-up.', 'error')
            return redirect(url_for('bookings.my_games'))
        
        # Check if booking is in the future
        if booking.booking_date <= date.today():
            flash('Cannot cancel past roll-up bookings.', 'error')
            return redirect(url_for('rollups.manage_rollup', booking_id=booking_id))
        
        # Delete the booking (this will cascade to BookingPlayer records)
        booking_info = f"Roll-up on {booking.booking_date} at session {booking.session}"
        db.session.delete(booking)
        db.session.commit()
        
        # Audit log
        audit_log_delete('Booking', booking_id, f'Cancelled roll-up booking: {booking_info}')
        
        flash('Roll-up booking cancelled successfully.', 'success')
        return redirect(url_for('bookings.my_games'))
        
    except Exception as e:
        current_app.logger.error(f"Error cancelling roll-up {booking_id}: {str(e)}")
        flash('An error occurred while cancelling the roll-up.', 'error')
        return redirect(url_for('bookings.my_games'))


# MOVED TO TEAMS BLUEPRINT: Player management is now handled through team management
# - Add/remove players: Use teams management page at /teams/manage/<team_id>
# - Rollup management now redirects to teams management for player operations