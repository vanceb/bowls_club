from flask import render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import login_required, current_user
from datetime import date, datetime
import sqlalchemy as sa

from app.rollups import bp
from app import db
from app.models import Booking, BookingPlayer, Member
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
            
            # Add organizer as confirmed player
            organizer_player = BookingPlayer(
                booking_id=booking.id,
                member_id=current_user.id,
                status='confirmed',
                invited_by=current_user.id,  # Organizer invites themselves
                response_at=datetime.utcnow()
            )
            db.session.add(organizer_player)
            
            # Add invited players
            if form.invited_players.data:
                invited_player_ids = [int(x.strip()) for x in form.invited_players.data.split(',') if x.strip()]
                for player_id in invited_player_ids:
                    if player_id != current_user.id:  # Don't invite organizer
                        invited_player = BookingPlayer(
                            booking_id=booking.id,
                            member_id=player_id,
                            status='pending',
                            invited_by=current_user.id  # Organizer invites other players
                        )
                        db.session.add(invited_player)
            
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
        
        # Get the player invitation
        invitation = db.session.scalar(
            sa.select(BookingPlayer)
            .where(
                BookingPlayer.booking_id == booking_id,
                BookingPlayer.member_id == current_user.id
            )
        )
        
        if not invitation:
            flash('You are not invited to this roll-up.', 'error')
            return redirect(url_for('bookings.my_games'))
        
        # Update the response
        if action == 'accept':
            invitation.status = 'confirmed'
            invitation.response_at = datetime.utcnow()
            flash('Roll-up invitation accepted!', 'success')
        elif action == 'decline':
            invitation.status = 'declined'
            invitation.response_at = datetime.utcnow()
            flash('Roll-up invitation declined.', 'info')
        else:
            flash('Invalid action.', 'error')
            return redirect(url_for('bookings.my_games'))
        
        db.session.commit()
        
        # Audit log
        audit_log_update('BookingPlayer', invitation.id, 
                       f'Updated roll-up response to {invitation.status}')
        
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
        
        # Get all players for this booking
        players = db.session.scalars(
            sa.select(BookingPlayer)
            .join(BookingPlayer.member)
            .where(BookingPlayer.booking_id == booking_id)
            .order_by(Member.firstname, Member.lastname)
        ).all()
        
        # Get session name
        sessions = current_app.config.get('DAILY_SESSIONS', {})
        session_name = sessions.get(booking.session, 'Unknown Session')
        
        # Create CSRF form
        csrf_form = FlaskForm()
        
        return render_template('manage_rollup.html', 
                             booking=booking,
                             players=players,
                             session_name=session_name,
                             today=date.today(),
                             csrf_form=csrf_form)
        
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


@bp.route('/remove_player/<int:booking_id>', methods=['POST'])
@login_required
def remove_rollup_player(booking_id):
    """
    Remove a player from a roll-up booking (organizer only)
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
            flash('You are not authorized to modify this roll-up.', 'error')
            return redirect(url_for('bookings.my_games'))
        
        # Get player ID from form
        player_id = request.form.get('player_id')
        if not player_id:
            flash('Missing player information.', 'error')
            return redirect(url_for('rollups.manage_rollup', booking_id=booking_id))
        
        # Get the player record
        player = db.session.get(BookingPlayer, player_id)
        if not player or player.booking_id != booking_id:
            flash('Invalid player record.', 'error')
            return redirect(url_for('rollups.manage_rollup', booking_id=booking_id))
        
        # Don't allow organizer to remove themselves
        if player.member_id == booking.organizer_id:
            flash('Organizer cannot be removed from the roll-up.', 'error')
            return redirect(url_for('rollups.manage_rollup', booking_id=booking_id))
        
        # Remove the player
        player_name = f"{player.member.firstname} {player.member.lastname}"
        db.session.delete(player)
        db.session.commit()
        
        # Audit log
        audit_log_delete('BookingPlayer', player_id, 
                        f'Removed player {player_name} from roll-up booking {booking_id}')
        
        flash(f'{player_name} has been removed from the roll-up.', 'success')
        return redirect(url_for('rollups.manage_rollup', booking_id=booking_id))
        
    except Exception as e:
        current_app.logger.error(f"Error removing player from roll-up {booking_id}: {str(e)}")
        flash('An error occurred while removing the player.', 'error')
        return redirect(url_for('bookings.my_games'))


@bp.route('/add_player/<int:booking_id>', methods=['POST'])
@login_required
def add_rollup_player(booking_id):
    """
    Add a player to a roll-up booking (organizer only)
    """
    try:
        current_app.logger.info(f"Add player request for booking {booking_id} by user {current_user.id}")
        
        # Validate CSRF
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            current_app.logger.error(f"CSRF validation failed for add player booking {booking_id}")
            flash('Security validation failed.', 'error')
            return redirect(url_for('bookings.my_games'))
        
        # Get the booking
        booking = db.session.get(Booking, booking_id)
        if not booking or booking.booking_type != 'rollup':
            flash('Invalid roll-up booking.', 'error')
            return redirect(url_for('bookings.my_games'))
        
        # Check if user is the organizer
        if booking.organizer_id != current_user.id:
            flash('You are not authorized to modify this roll-up.', 'error')
            return redirect(url_for('bookings.my_games'))
        
        # Get member ID from form
        member_id = request.form.get('member_id')
        current_app.logger.info(f"Received member_id: {member_id}")
        if not member_id:
            current_app.logger.error(f"Missing member_id in form data")
            flash('Missing member information.', 'error')
            return redirect(url_for('rollups.manage_rollup', booking_id=booking_id))
        
        # Get the member
        member = db.session.get(Member, int(member_id))
        if not member:
            flash('Member not found.', 'error')
            return redirect(url_for('rollups.manage_rollup', booking_id=booking_id))
        
        # Check if member is already in the roll-up
        existing_player = db.session.scalar(
            sa.select(BookingPlayer).where(
                BookingPlayer.booking_id == booking_id,
                BookingPlayer.member_id == member_id
            )
        )
        if existing_player:
            flash(f'{member.firstname} {member.lastname} is already in this roll-up.', 'warning')
            return redirect(url_for('rollups.manage_rollup', booking_id=booking_id))
        
        # Check roll-up capacity
        current_players = db.session.scalar(
            sa.select(sa.func.count(BookingPlayer.id)).where(BookingPlayer.booking_id == booking_id)
        )
        max_players = current_app.config.get('ROLLUP_MAX_PLAYERS', 8)
        if current_players >= max_players:
            flash(f'Roll-up is full (maximum {max_players} players).', 'error')
            return redirect(url_for('rollups.manage_rollup', booking_id=booking_id))
        
        # Add the player
        new_player = BookingPlayer(
            booking_id=booking_id,
            member_id=member_id,
            status='pending',
            invited_by=current_user.id,
            response_at=datetime.utcnow()
        )
        db.session.add(new_player)
        db.session.commit()
        
        # Audit log
        player_name = f"{member.firstname} {member.lastname}"
        audit_log_create('BookingPlayer', new_player.id, 
                        f'Added player {player_name} to roll-up booking {booking_id}')
        
        current_app.logger.info(f"Successfully added player {player_name} to booking {booking_id}")
        flash(f'{player_name} has been added to the roll-up.', 'success')
        return redirect(url_for('rollups.manage_rollup', booking_id=booking_id))
        
    except Exception as e:
        current_app.logger.error(f"Error adding player to roll-up {booking_id}: {str(e)}")
        flash('An error occurred while adding the player.', 'error')
        return redirect(url_for('bookings.my_games'))