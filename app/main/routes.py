# Main public routes for the Bowls Club application
import os
from datetime import datetime, timedelta, date
from flask import render_template, flash, redirect, url_for, request, abort, jsonify, current_app
from flask_login import current_user, login_required
from flask_paginate import Pagination, get_page_parameter
import sqlalchemy as sa

from app.main import bp
from app import db
from app.models import Member, Post, Booking, Event, PolicyPage, BookingPlayer, EventPool, PoolRegistration
from app.utils import sanitize_html_content, get_secure_post_path
from app.forms import RollUpResponseForm, FlaskForm
from app.routes import role_required


@bp.route("/")
@bp.route("/index")
@login_required
def index():
    """
    Home page that displays recent posts and upcoming events
    """
    try:
        today = date.today()
        
        # Fetch pinned posts (posts with pin_until date >= today)
        pinned_posts = db.session.scalars(
            sa.select(Post).where(
                Post.expires_on >= today,
                Post.pin_until >= today
            )
            .order_by(Post.publish_on.desc())
        ).all()
        
        # Fetch non-pinned posts (posts without pin_until or pin_until < today)
        non_pinned_posts = db.session.scalars(
            sa.select(Post).where(
                Post.expires_on >= today,
                sa.or_(Post.pin_until < today, Post.pin_until == None)
            )
            .order_by(Post.publish_on.desc())
            .limit(5)  # Show 5 recent non-pinned posts
        ).all()
        
        # Get upcoming events (next 7 days)
        upcoming_events = db.session.scalars(
            sa.select(Booking)
            .join(Event)
            .where(
                Booking.booking_date >= today,
                Booking.booking_date <= today + timedelta(days=7)
            )
            .order_by(Booking.booking_date, Booking.session)
        ).all()
        
        return render_template('main/index.html', 
                             recent_posts=non_pinned_posts,  # Keep for backwards compatibility
                             upcoming_events=upcoming_events,
                             pinned_posts=pinned_posts,
                             non_pinned_posts=non_pinned_posts,
                             pagination=None,
                             current_page=1)
    except Exception as e:
        current_app.logger.error(f"Error in index route: {str(e)}")
        flash('An error occurred while loading the home page.', 'error')
        return render_template('main/index.html', 
                             recent_posts=[], 
                             upcoming_events=[],
                             pinned_posts=[],
                             non_pinned_posts=[],
                             pagination=None,
                             current_page=1)


@bp.route("/post/<int:post_id>")
@login_required
def post(post_id):
    """
    Display a single post with full content
    """
    try:
        # Get post by ID
        post = db.session.get(Post, post_id)
        if not post:
            current_app.logger.error(f"Post not found with ID: {post_id}")
            abort(404)
        
        current_app.logger.info(f"Found post: {post.title}, HTML file: {post.html_filename}")
        
        # Get the HTML content from secure storage using utility function
        html_path = get_secure_post_path(post.html_filename)
        
        if not html_path:
            current_app.logger.error(f"Could not get secure path for HTML file: {post.html_filename}")
            abort(404)
            
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except FileNotFoundError:
            current_app.logger.error(f"Post HTML file not found: {html_path}")
            abort(404)
        except Exception as e:
            current_app.logger.error(f"Error reading HTML file {html_path}: {str(e)}")
            abort(500)
        
        # Sanitize HTML content
        try:
            sanitized_content = sanitize_html_content(html_content)
        except Exception as e:
            current_app.logger.error(f"Error sanitizing HTML content: {str(e)}")
            sanitized_content = html_content  # Fallback to unsanitized content
        
        return render_template('main/view_post.html', post=post, content=sanitized_content)
    except Exception as e:
        current_app.logger.error(f"Error displaying post {post_id}: {str(e)}")
        abort(500)


@bp.route('/members')
@login_required
def members():
    """
    Display paginated list of active members
    """
    try:
        # Get page parameter
        page = request.args.get(get_page_parameter(), type=int, default=1)
        per_page = 20
        
        # Get active members (Full, Social, Life)
        members_query = sa.select(Member).where(
            Member.status.in_(['Full', 'Social', 'Life'])
        ).order_by(Member.lastname, Member.firstname)
        
        # Get total count for pagination
        total = db.session.scalar(sa.select(sa.func.count()).select_from(members_query.subquery()))
        
        # Get paginated members
        members = db.session.scalars(
            members_query.offset((page - 1) * per_page).limit(per_page)
        ).all()
        
        # Create pagination object
        pagination = Pagination(page=page, per_page=per_page, total=total,
                               css_framework='bulma')
        
        return render_template('main/members.html', 
                             members=members, 
                             pagination=pagination,
                             total=total)
    except Exception as e:
        current_app.logger.error(f"Error in members route: {str(e)}")
        flash('An error occurred while loading the members page.', 'error')
        return render_template('main/members.html', members=[], pagination=None, total=0)


@bp.route('/bookings')
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
        
        return render_template('main/bookings_table.html', 
                             today=today.isoformat(),
                             sessions=sessions,
                             rinks=rinks)
    except Exception as e:
        current_app.logger.error(f"Error in bookings route: {str(e)}")
        flash('An error occurred while loading the bookings page.', 'error')
        return render_template('main/bookings_table.html', 
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


@bp.route('/policy/<slug>')
@login_required
def policy(slug):
    """
    Display a policy page by slug
    """
    try:
        # Get policy page by slug
        policy_page = db.session.scalar(
            sa.select(PolicyPage)
            .where(PolicyPage.slug == slug, PolicyPage.is_active == True)
        )
        
        if not policy_page:
            abort(404)
        
        # Get the HTML content from file
        from app.utils import get_secure_policy_page_path
        html_path = get_secure_policy_page_path(policy_page.html_filename)
        if not html_path:
            abort(404)
        
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except FileNotFoundError:
            abort(404)
        
        # Sanitize HTML content
        sanitized_content = sanitize_html_content(html_content)
        
        return render_template('main/view_policy_page.html', 
                             policy_page=policy_page, 
                             content=sanitized_content)
    except Exception as e:
        current_app.logger.error(f"Error displaying policy {slug}: {str(e)}")
        abort(500)


@bp.route('/upcoming_events')
@login_required
def upcoming_events():
    """
    Display upcoming events that are open for registration
    Show user's registration status for each event
    """
    try:
        from app.audit import audit_log_create, audit_log_delete
        from app.forms import FlaskForm
        
        # Create CSRF form for the template
        csrf_form = FlaskForm()
        
        # Get today's date
        today = date.today()
        
        # Get all events that have pools enabled
        events_with_pools = db.session.scalars(
            sa.select(Event)
            .where(Event.has_pool == True)
            .order_by(Event.created_at.desc())
        ).all()
        
        # For each event, get the user's registration status
        events_data = []
        for event in events_with_pools:
            # Skip events that claim to have pools but don't actually have pool records
            if not event.pool:
                current_app.logger.warning(f"Event {event.name} (ID: {event.id}) has has_pool=True but no pool record")
                continue
                
            event_info = {
                'event': event,
                'registration_status': 'not_registered',
                'registration': None,
                'pool_count': event.get_pool_member_count(),
                'pool_open': event.is_pool_open()
            }
            
            # Check if user is registered
            user_registration = event.pool.get_member_registration(current_user.id)
            if user_registration:
                event_info['registration'] = user_registration
                event_info['registration_status'] = 'registered'  # All pool registrations are 'registered' by existence
            
            events_data.append(event_info)
        
        return render_template('main/upcoming_events.html', 
                             events_data=events_data,
                             today=today,
                             csrf_form=csrf_form)
                             
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"Error in upcoming_events route: {str(e)}")
        current_app.logger.error(f"Full traceback: {error_details}")
        flash(f'An error occurred while loading upcoming events: {str(e)}', 'error')
        from app.forms import FlaskForm
        csrf_form = FlaskForm()
        return render_template('main/upcoming_events.html', 
                             events_data=[],
                             today=date.today(),
                             csrf_form=csrf_form)


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
            
            return redirect(url_for('main.my_games'))
        
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
        
        return render_template('main/my_games.html', 
                             assignments=assignments,
                             roll_up_invitations=roll_up_invitations,
                             today=today,
                             csrf_form=csrf_form)
                             
    except Exception as e:
        current_app.logger.error(f"Error in my_games route: {str(e)}")
        flash('An error occurred while loading your games.', 'error')
        return render_template('main/my_games.html', 
                             assignments=[], 
                             roll_up_invitations=[],
                             today=date.today(),
                             csrf_form=FlaskForm())


@bp.route('/rollup/book', methods=['GET', 'POST'])
@login_required
def book_rollup():
    """
    Book a roll-up game and invite players
    """
    try:
        from app.forms import RollUpBookingForm
        from app.audit import audit_log_create
        
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
            return redirect(url_for('main.my_games'))
        
        return render_template('main/book_rollup.html', form=form)
        
    except Exception as e:
        current_app.logger.error(f"Error in book_rollup route: {str(e)}")
        flash('An error occurred while booking the roll-up.', 'error')
        return redirect(url_for('main.my_games'))


@bp.route('/rollup/respond/<int:booking_id>/<action>')
@login_required
def respond_to_rollup(booking_id, action):
    """
    Respond to a roll-up invitation
    """
    try:
        from app.audit import audit_log_update
        
        # Get the booking
        booking = db.session.get(Booking, booking_id)
        if not booking or booking.booking_type != 'rollup':
            flash('Invalid roll-up booking.', 'error')
            return redirect(url_for('main.my_games'))
        
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
            return redirect(url_for('main.my_games'))
        
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
            return redirect(url_for('main.my_games'))
        
        db.session.commit()
        
        # Audit log
        audit_log_update('BookingPlayer', invitation.id, 
                       f'Updated roll-up response to {invitation.status}')
        
        return redirect(url_for('main.my_games'))
        
    except Exception as e:
        current_app.logger.error(f"Error responding to roll-up {booking_id}: {str(e)}")
        flash('An error occurred while responding to the roll-up.', 'error')
        return redirect(url_for('main.my_games'))


@bp.route('/rollup/manage/<int:booking_id>')
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
        from app.forms import FlaskForm
        csrf_form = FlaskForm()
        
        return render_template('main/manage_rollup.html', 
                             booking=booking,
                             players=players,
                             session_name=session_name,
                             today=date.today(),
                             csrf_form=csrf_form)
        
    except Exception as e:
        current_app.logger.error(f"Error managing roll-up {booking_id}: {str(e)}")
        flash('An error occurred while loading the roll-up management page.', 'error')
        return redirect(url_for('main.my_games'))


@bp.route('/rollup/cancel/<int:booking_id>', methods=['POST'])
@login_required
def cancel_rollup(booking_id):
    """
    Cancel a roll-up booking (organizer only)
    """
    try:
        from app.forms import FlaskForm
        from app.audit import audit_log_delete
        
        # Validate CSRF
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('main.my_games'))
        
        # Get the booking
        booking = db.session.get(Booking, booking_id)
        if not booking or booking.booking_type != 'rollup':
            flash('Invalid roll-up booking.', 'error')
            return redirect(url_for('main.my_games'))
        
        # Check if user is the organizer
        if booking.organizer_id != current_user.id:
            flash('You are not authorized to cancel this roll-up.', 'error')
            return redirect(url_for('main.my_games'))
        
        # Check if booking is in the future
        if booking.booking_date <= date.today():
            flash('Cannot cancel past roll-up bookings.', 'error')
            return redirect(url_for('main.manage_rollup', booking_id=booking_id))
        
        # Delete the booking (this will cascade to BookingPlayer records)
        booking_info = f"Roll-up on {booking.booking_date} at session {booking.session}"
        db.session.delete(booking)
        db.session.commit()
        
        # Audit log
        audit_log_delete('Booking', booking_id, f'Cancelled roll-up booking: {booking_info}')
        
        flash('Roll-up booking cancelled successfully.', 'success')
        return redirect(url_for('main.my_games'))
        
    except Exception as e:
        current_app.logger.error(f"Error cancelling roll-up {booking_id}: {str(e)}")
        flash('An error occurred while cancelling the roll-up.', 'error')
        return redirect(url_for('main.my_games'))


@bp.route('/rollup/remove_player/<int:booking_id>', methods=['POST'])
@login_required
def remove_rollup_player(booking_id):
    """
    Remove a player from a roll-up booking (organizer only)
    """
    try:
        from app.forms import FlaskForm
        from app.audit import audit_log_delete
        
        # Validate CSRF
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('main.my_games'))
        
        # Get the booking
        booking = db.session.get(Booking, booking_id)
        if not booking or booking.booking_type != 'rollup':
            flash('Invalid roll-up booking.', 'error')
            return redirect(url_for('main.my_games'))
        
        # Check if user is the organizer
        if booking.organizer_id != current_user.id:
            flash('You are not authorized to modify this roll-up.', 'error')
            return redirect(url_for('main.my_games'))
        
        # Get player ID from form
        player_id = request.form.get('player_id')
        if not player_id:
            flash('Missing player information.', 'error')
            return redirect(url_for('main.manage_rollup', booking_id=booking_id))
        
        # Get the player record
        player = db.session.get(BookingPlayer, player_id)
        if not player or player.booking_id != booking_id:
            flash('Invalid player record.', 'error')
            return redirect(url_for('main.manage_rollup', booking_id=booking_id))
        
        # Don't allow organizer to remove themselves
        if player.member_id == booking.organizer_id:
            flash('Organizer cannot be removed from the roll-up.', 'error')
            return redirect(url_for('main.manage_rollup', booking_id=booking_id))
        
        # Remove the player
        player_name = f"{player.member.firstname} {player.member.lastname}"
        db.session.delete(player)
        db.session.commit()
        
        # Audit log
        audit_log_delete('BookingPlayer', player_id, 
                        f'Removed player {player_name} from roll-up booking {booking_id}')
        
        flash(f'{player_name} has been removed from the roll-up.', 'success')
        return redirect(url_for('main.manage_rollup', booking_id=booking_id))
        
    except Exception as e:
        current_app.logger.error(f"Error removing player from roll-up {booking_id}: {str(e)}")
        flash('An error occurred while removing the player.', 'error')
        return redirect(url_for('main.my_games'))


@bp.route('/rollup/add_player/<int:booking_id>', methods=['POST'])
@login_required
def add_rollup_player(booking_id):
    """
    Add a player to a roll-up booking (organizer only)
    """
    try:
        from app.forms import FlaskForm
        from app.audit import audit_log_create
        
        current_app.logger.info(f"Add player request for booking {booking_id} by user {current_user.id}")
        
        # Validate CSRF
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            current_app.logger.error(f"CSRF validation failed for add player booking {booking_id}")
            flash('Security validation failed.', 'error')
            return redirect(url_for('main.my_games'))
        
        # Get the booking
        booking = db.session.get(Booking, booking_id)
        if not booking or booking.booking_type != 'rollup':
            flash('Invalid roll-up booking.', 'error')
            return redirect(url_for('main.my_games'))
        
        # Check if user is the organizer
        if booking.organizer_id != current_user.id:
            flash('You are not authorized to modify this roll-up.', 'error')
            return redirect(url_for('main.my_games'))
        
        # Get member ID from form
        member_id = request.form.get('member_id')
        current_app.logger.info(f"Received member_id: {member_id}")
        if not member_id:
            current_app.logger.error(f"Missing member_id in form data")
            flash('Missing member information.', 'error')
            return redirect(url_for('main.manage_rollup', booking_id=booking_id))
        
        # Get the member
        member = db.session.get(Member, int(member_id))
        if not member:
            flash('Member not found.', 'error')
            return redirect(url_for('main.manage_rollup', booking_id=booking_id))
        
        # Check if member is already in the roll-up
        existing_player = db.session.scalar(
            sa.select(BookingPlayer).where(
                BookingPlayer.booking_id == booking_id,
                BookingPlayer.member_id == member_id
            )
        )
        if existing_player:
            flash(f'{member.firstname} {member.lastname} is already in this roll-up.', 'warning')
            return redirect(url_for('main.manage_rollup', booking_id=booking_id))
        
        # Check roll-up capacity
        current_players = db.session.scalar(
            sa.select(sa.func.count(BookingPlayer.id)).where(BookingPlayer.booking_id == booking_id)
        )
        max_players = current_app.config.get('ROLLUP_MAX_PLAYERS', 8)
        if current_players >= max_players:
            flash(f'Roll-up is full (maximum {max_players} players).', 'error')
            return redirect(url_for('main.manage_rollup', booking_id=booking_id))
        
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
        return redirect(url_for('main.manage_rollup', booking_id=booking_id))
        
    except Exception as e:
        current_app.logger.error(f"Error adding player to roll-up {booking_id}: {str(e)}")
        flash('An error occurred while adding the player.', 'error')
        return redirect(url_for('main.my_games'))


@bp.route('/add_member', methods=['GET', 'POST'])
def add_member():
    """
    Add a new member to the system
    Handles both bootstrap mode (first user) and normal member creation
    """
    try:
        from app.forms import MemberForm
        from app.audit import audit_log_create
        from werkzeug.security import generate_password_hash
        
        # Check if we're in bootstrap mode (no users exist)
        is_bootstrap = Member.is_bootstrap_mode()
        
        # If not bootstrap mode, require login and User Manager role
        if not is_bootstrap:
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if not current_user.has_role('User Manager'):
                abort(403)
        
        form = MemberForm()
        
        if form.validate_on_submit():
            # Create new member
            member = Member(
                username=form.username.data,
                firstname=form.firstname.data,
                lastname=form.lastname.data,
                email=form.email.data,
                phone=form.phone.data,
                share_email=form.share_email.data,
                share_phone=form.share_phone.data,
            )
            
            # Bootstrap mode: first user automatically becomes admin with all roles
            if is_bootstrap:
                member.is_admin = True
                member.status = 'Active'
                # Assign all roles to first user
                from app.models import Role
                member.roles = Role.query.all()
            else:
                # Normal mode: use form values
                member.status = form.status.data
                member.is_admin = form.is_admin.data
            
            # Set password if provided
            if form.password.data:
                member.set_password(form.password.data)
            
            db.session.add(member)
            db.session.commit()
            
            # Audit log
            audit_log_create('Member', member.id, 
                           f'Created member: {member.firstname} {member.lastname} ({member.username})',
                           {'status': member.status, 'is_admin': member.is_admin, 'bootstrap': is_bootstrap})
            
            if is_bootstrap:
                flash(f'Welcome! Admin user {member.firstname} {member.lastname} has been created successfully. You now have full access to the system.', 'success')
                return redirect(url_for('auth.login'))
            else:
                flash(f'Member {member.firstname} {member.lastname} has been added successfully.', 'success')
                return redirect(url_for('main.members'))
        
        return render_template('main/add_member.html', form=form, is_bootstrap=is_bootstrap)
        
    except Exception as e:
        current_app.logger.error(f"Error adding member: {str(e)}")
        flash('An error occurred while adding the member.', 'error')
        return render_template('main/add_member.html', form=MemberForm(), is_bootstrap=is_bootstrap)


@bp.route('/register_for_event', methods=['POST'])
@login_required
def register_for_event():
    """
    Register current user for an event pool
    """
    try:
        from app.audit import audit_log_create
        from app.forms import FlaskForm
        
        # Validate CSRF
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('main.upcoming_events'))
        
        event_id = request.form.get('event_id')
        if not event_id:
            flash('Missing event information.', 'error')
            return redirect(url_for('main.upcoming_events'))
        
        # Get the event
        event = db.session.get(Event, int(event_id))
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('main.upcoming_events'))
        
        # Check if event has pool enabled
        if not event.has_pool_enabled():
            flash('This event does not have pool registration enabled.', 'error')
            return redirect(url_for('main.upcoming_events'))
        
        # Check if pool is open
        if not event.is_pool_open():
            flash('Registration for this event is closed.', 'warning')
            return redirect(url_for('main.upcoming_events'))
        
        # Check if user is already registered
        existing_registration = event.pool.get_member_registration(current_user.id)
        if existing_registration and existing_registration.is_active:
            flash(f'You are already registered for {event.name}.', 'warning')
            return redirect(url_for('main.upcoming_events'))
        
        # Create new registration
        registration = PoolRegistration(
            pool_id=event.pool.id,
            member_id=current_user.id
        )
        
        db.session.add(registration)
        db.session.commit()
        
        # Audit log
        audit_log_create('PoolRegistration', registration.id, 
                        f'User {current_user.username} registered for event: {event.name}')
        
        flash(f'Successfully registered for {event.name}!', 'success')
        return redirect(url_for('main.upcoming_events'))
        
    except Exception as e:
        current_app.logger.error(f"Error registering for event: {str(e)}")
        flash('An error occurred while registering for the event.', 'error')
        return redirect(url_for('main.upcoming_events'))


@bp.route('/withdraw_from_event', methods=['POST'])
@login_required
def withdraw_from_event():
    """
    Withdraw current user from an event pool
    """
    try:
        from app.audit import audit_log_update
        from app.forms import FlaskForm
        
        # Validate CSRF
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('main.upcoming_events'))
        
        event_id = request.form.get('event_id')
        if not event_id:
            flash('Missing event information.', 'error')
            return redirect(url_for('main.upcoming_events'))
        
        # Get the event
        event = db.session.get(Event, int(event_id))
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('main.upcoming_events'))
        
        # Check if event has pool enabled
        if not event.has_pool_enabled():
            flash('This event does not have pool registration.', 'error')
            return redirect(url_for('main.upcoming_events'))
        
        # Get user's registration
        registration = event.pool.get_member_registration(current_user.id)
        if not registration or not registration.is_active:
            flash(f'You are not registered for {event.name}.', 'warning')
            return redirect(url_for('main.upcoming_events'))
        
        # Check if pool is still open
        if not event.is_pool_open():
            flash('Registration for this event is closed. Contact the event manager to make changes.', 'warning')
            return redirect(url_for('main.upcoming_events'))
        
        # Remove the registration entirely
        registration_id = registration.id
        db.session.delete(registration)
        db.session.commit()
        
        # Audit log
        from app.audit import audit_log_delete
        audit_log_delete('PoolRegistration', registration_id, 
                        f'User {current_user.username} withdrew from event: {event.name}')
        
        flash(f'Successfully withdrawn from {event.name}.', 'success')
        return redirect(url_for('main.upcoming_events'))
        
    except Exception as e:
        current_app.logger.error(f"Error withdrawing from event: {str(e)}")
        flash('An error occurred while withdrawing from the event.', 'error')
        return redirect(url_for('main.upcoming_events'))


