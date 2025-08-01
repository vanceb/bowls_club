# Main public routes for the Bowls Club application
import os
from datetime import datetime, timedelta, date
from flask import render_template, flash, redirect, url_for, request, abort, jsonify, current_app
from flask_login import current_user, login_required
from flask_paginate import Pagination, get_page_parameter
import sqlalchemy as sa

from app.main import bp
from app import db
from app.models import Member, Post, Booking, Event, Pool, PoolRegistration
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


# MOVED TO MEMBERS BLUEPRINT: /members → /members/directory


# MOVED TO BOOKINGS BLUEPRINT: booking functionality has been moved to the bookings blueprint
# - Main bookings view: /bookings/
# - AJAX endpoints: /bookings/get_bookings/<date> and /bookings/get_bookings_range/<start>/<end>




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
        
        # Import models needed for queries
        from app.models import Pool, PoolRegistration, Booking
        
        # Get all events that have any type of pool or user relationship
        # Start with events that have event-level pools OR booking-level pools (has_pool flag)
        events_with_pools = db.session.scalars(
            sa.select(Event)
            .where(Event.has_pool == True)
            .order_by(Event.created_at.desc())
        ).all()
        
        # Fallback: Also get events that actually have pool records but may have incorrect has_pool flag
        # This handles data inconsistencies where pools exist but has_pool=False
        events_with_actual_event_pools = db.session.scalars(
            sa.select(Event)
            .join(Pool, Event.id == Pool.event_id)
            .where(Event.has_pool == False)  # Only get ones not already captured above
            .order_by(Event.created_at.desc())
        ).all()
        
        events_with_actual_booking_pools = db.session.scalars(
            sa.select(Event)
            .join(Booking, Event.id == Booking.event_id)
            .join(Pool, Booking.id == Pool.booking_id)
            .where(Event.has_pool == False)  # Only get ones not already captured above
            .order_by(Event.created_at.desc())
        ).all()
        
        # Get events where user is registered in event-level pools
        events_user_registered_event_pools = db.session.scalars(
            sa.select(Event)
            .join(Pool, Event.id == Pool.event_id)
            .join(PoolRegistration, Pool.id == PoolRegistration.pool_id)
            .where(PoolRegistration.member_id == current_user.id)
            .order_by(Event.created_at.desc())
        ).all()
        
        # Get events where user is registered in booking-level pools
        events_user_registered_booking_pools = db.session.scalars(
            sa.select(Event)
            .join(Booking, Event.id == Booking.event_id)
            .join(Pool, Booking.id == Pool.booking_id)
            .join(PoolRegistration, Pool.id == PoolRegistration.pool_id)
            .where(PoolRegistration.member_id == current_user.id)
            .order_by(Event.created_at.desc())
        ).all()
        
        # Get events the user can manage (includes admin, global event managers, and specific event managers)
        events_user_manages = []
        if current_user.is_admin or current_user.has_role('Event Manager'):
            # Admin and global event managers can see all events with pools
            events_user_manages = events_with_pools
        else:
            # Specific event managers only see their assigned events
            events_user_manages = db.session.scalars(
                sa.select(Event)
                .join(Event.event_managers)
                .where(
                    Event.event_managers.any(Member.id == current_user.id),
                    Event.has_pool == True
                )
                .order_by(Event.created_at.desc())
            ).all()
        
        # Combine and deduplicate events
        all_events = list({event.id: event for event in 
                          events_with_pools + 
                          events_with_actual_event_pools + 
                          events_with_actual_booking_pools +
                          events_user_registered_event_pools + 
                          events_user_registered_booking_pools + 
                          events_user_manages}.values())
        all_events.sort(key=lambda x: x.created_at, reverse=True)
        
        # For each event, get the user's registration status and management permissions
        events_data = []
        for event in all_events:
            # Check if user can manage this event
            from app.events.utils import can_user_manage_event, get_event_pool_info
            user_can_manage = can_user_manage_event(current_user, event)
            
            # Get comprehensive pool information (handles both event-level and booking-level pools)
            pool_info = get_event_pool_info(event)
            
            # Skip events that don't actually have any pools
            if not pool_info['has_pools']:
                continue
                
            event_info = {
                'event': event,
                'registration_status': 'not_registered',
                'registration': None,
                'pool_count': pool_info['total_members'],
                'pool_open': pool_info['pool_status'] in ['open', 'mixed'],
                'user_can_manage': user_can_manage,
                'pool_info': pool_info
            }
            
            # Check if user is registered in any pools for this event
            user_registration = None
            
            # Check event-level pool first
            if event.pool:
                user_registration = event.pool.get_member_registration(current_user.id)
            
            # If not found in event pool, check booking-level pools
            if not user_registration:
                for booking in event.bookings:
                    if booking.pool:
                        user_registration = booking.pool.get_member_registration(current_user.id)
                        if user_registration:
                            break
            
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


