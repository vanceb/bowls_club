# Main public routes for the Bowls Club application
import os
from datetime import datetime, timedelta, date
from flask import render_template, flash, redirect, url_for, request, abort, jsonify, current_app
from flask_login import current_user, login_required
from flask_paginate import Pagination, get_page_parameter
import sqlalchemy as sa

from app.main import bp
from app import db
from app.models import Member, Post, Booking, Pool, PoolRegistration
from app.forms import FlaskForm
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


# MOVED TO MEMBERS BLUEPRINT: /members → /members/directory


# MOVED TO BOOKINGS BLUEPRINT: booking functionality has been moved to the bookings blueprint
# - Main bookings view: /bookings/
# - AJAX endpoints: /bookings/get_bookings/<date> and /bookings/get_bookings_range/<start>/<end>




@bp.route('/upcoming_events')
@login_required
def upcoming_events():
    """
    Display upcoming events (bookings) that are open for registration
    Show user's registration status for each event
    """
    try:
        from app.audit import audit_log_create, audit_log_delete
        from app.forms import FlaskForm
        
        # Create CSRF form for the template
        csrf_form = FlaskForm()
        
        # Get today's date
        today = date.today()
        
        # Import models needed for queries
        from app.models import Pool, PoolRegistration, Booking
        
        # Get all bookings (events) that have pools enabled
        bookings_with_pools = db.session.scalars(
            sa.select(Booking)
            .where(Booking.has_pool == True)
            .order_by(Booking.created_at_event.desc())
        ).all()
        
        # Fallback: Get bookings that actually have pool records but may have incorrect has_pool flag
        # This handles data inconsistencies where pools exist but has_pool=False
        bookings_with_actual_pools = db.session.scalars(
            sa.select(Booking)
            .join(Pool, Booking.id == Pool.booking_id)
            .where(Booking.has_pool == False)  # Only get ones not already captured above
            .order_by(Booking.created_at_event.desc())
        ).all()
        
        # Get bookings where user is registered in pools
        bookings_user_registered = db.session.scalars(
            sa.select(Booking)
            .join(Pool, Booking.id == Pool.booking_id)
            .join(PoolRegistration, Pool.id == PoolRegistration.pool_id)
            .where(PoolRegistration.member_id == current_user.id)
            .order_by(Booking.created_at_event.desc())
        ).all()
        
        # Get bookings the user can manage (includes admin, global event managers, and specific booking managers)
        bookings_user_manages = []
        if current_user.is_admin or current_user.has_role('Event Manager'):
            # Admin and global event managers can see all bookings with pools
            bookings_user_manages = bookings_with_pools
        else:
            # Specific booking managers only see their assigned bookings
            bookings_user_manages = db.session.scalars(
                sa.select(Booking)
                .join(Booking.booking_managers)
                .where(
                    Booking.booking_managers.any(Member.id == current_user.id),
                    Booking.has_pool == True
                )
                .order_by(Booking.created_at_event.desc())
            ).all()
        
        # Combine and deduplicate bookings
        all_bookings = list({booking.id: booking for booking in 
                           bookings_with_pools + 
                           bookings_with_actual_pools +
                           bookings_user_registered + 
                           bookings_user_manages}.values())
        all_bookings.sort(key=lambda x: x.created_at_event or datetime.now(), reverse=True)
        
        # For each booking, get the user's registration status and management permissions
        events_data = []
        for booking in all_bookings:
            # Check if user can manage this booking
            user_can_manage = (current_user.is_admin or 
                             current_user.has_role('Event Manager') or
                             current_user in booking.booking_managers)
            
            # Get pool information for this booking
            pool = booking.pool if hasattr(booking, 'pool') else None
            has_pools = pool is not None
            pool_open = pool.is_open if pool else False
            pool_count = len(pool.registrations) if pool else 0
            
            # Skip bookings that don't actually have any pools
            if not has_pools:
                continue
                
            event_info = {
                'event': booking,  # Keep 'event' key for template compatibility
                'registration_status': 'not_registered',
                'registration': None,
                'pool_count': pool_count,
                'pool_open': pool_open,
                'user_can_manage': user_can_manage,
                'pool_info': {
                    'has_pools': has_pools,
                    'total_members': pool_count,
                    'pool_status': 'open' if pool_open else 'closed'
                }
            }
            
            # Check if user is registered in the pool
            user_registration = None
            if pool:
                user_registration = pool.get_member_registration(current_user.id)
            
            if user_registration:
                event_info['registration'] = user_registration
                event_info['registration_status'] = 'registered'
            
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


# MOVED TO BOOKINGS BLUEPRINT: my_games functionality has been moved to the bookings blueprint
# - My games view: /bookings/my_games


# MOVED TO BOOKINGS BLUEPRINT: rollup functionality has been moved to the bookings blueprint
# - Book rollup: /bookings/rollup/book
# - Manage rollup: /bookings/rollup/manage/<id>
# - Respond to rollup: /bookings/rollup/respond/<id>/<action>
# - Cancel rollup: /bookings/rollup/cancel/<id>
# - Add/remove players: /bookings/rollup/add_player/<id> and /bookings/rollup/remove_player/<id>


# MOVED TO MEMBERS BLUEPRINT: add_member functionality has been moved to the members blueprint
# - Public member applications: /members/apply
# - Admin member creation: handled through admin routes in members blueprint


@bp.route('/register_for_event', methods=['POST'])
@login_required
def register_for_event():
    """
    Register current user for a booking (event) pool
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
        
        # Get the booking (event)
        booking = db.session.get(Booking, int(event_id))
        if not booking:
            flash('Event not found.', 'error')
            return redirect(url_for('main.upcoming_events'))
        
        # Check if booking has pool enabled
        if not booking.has_pool:
            flash('This event does not have pool registration enabled.', 'error')
            return redirect(url_for('main.upcoming_events'))
        
        # Get the pool for this booking
        pool = booking.pool if hasattr(booking, 'pool') else None
        if not pool:
            flash('No pool found for this event.', 'error')
            return redirect(url_for('main.upcoming_events'))
        
        # Check if pool is open
        if not pool.is_open:
            flash('Registration for this event is closed.', 'warning')
            return redirect(url_for('main.upcoming_events'))
        
        # Check if user is already registered
        existing_registration = pool.get_member_registration(current_user.id)
        if existing_registration and existing_registration.is_active:
            flash(f'You are already registered for {booking.name}.', 'warning')
            return redirect(url_for('main.upcoming_events'))
        
        # Create new registration
        registration = PoolRegistration(
            pool_id=pool.id,
            member_id=current_user.id
        )
        
        db.session.add(registration)
        db.session.commit()
        
        # Audit log
        audit_log_create('PoolRegistration', registration.id, 
                        f'User {current_user.username} registered for event: {booking.name}')
        
        flash(f'Successfully registered for {booking.name}!', 'success')
        return redirect(url_for('main.upcoming_events'))
        
    except Exception as e:
        current_app.logger.error(f"Error registering for event: {str(e)}")
        flash('An error occurred while registering for the event.', 'error')
        return redirect(url_for('main.upcoming_events'))


@bp.route('/withdraw_from_event', methods=['POST'])
@login_required
def withdraw_from_event():
    """
    Withdraw current user from a booking (event) pool
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
        
        # Get the booking (event)
        booking = db.session.get(Booking, int(event_id))
        if not booking:
            flash('Event not found.', 'error')
            return redirect(url_for('main.upcoming_events'))
        
        # Check if booking has pool enabled
        if not booking.has_pool:
            flash('This event does not have pool registration.', 'error')
            return redirect(url_for('main.upcoming_events'))
        
        # Get the pool for this booking
        pool = booking.pool if hasattr(booking, 'pool') else None
        if not pool:
            flash('No pool found for this event.', 'error')
            return redirect(url_for('main.upcoming_events'))
        
        # Get user's registration
        registration = pool.get_member_registration(current_user.id)
        if not registration or not registration.is_active:
            flash(f'You are not registered for {booking.name}.', 'warning')
            return redirect(url_for('main.upcoming_events'))
        
        # Check if pool is still open
        if not pool.is_open:
            flash('Registration for this event is closed. Contact the event manager to make changes.', 'warning')
            return redirect(url_for('main.upcoming_events'))
        
        # Remove the registration entirely
        registration_id = registration.id
        db.session.delete(registration)
        db.session.commit()
        
        # Audit log
        from app.audit import audit_log_delete
        audit_log_delete('PoolRegistration', registration_id, 
                        f'User {current_user.username} withdrew from event: {booking.name}')
        
        flash(f'Successfully withdrawn from {booking.name}.', 'success')
        return redirect(url_for('main.upcoming_events'))
        
    except Exception as e:
        current_app.logger.error(f"Error withdrawing from event: {str(e)}")
        flash('An error occurred while withdrawing from the event.', 'error')
        return redirect(url_for('main.upcoming_events'))


