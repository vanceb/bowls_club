"""
Base event management routes.

This module provides core event management functionality that can be
extended by specialized event type blueprints (leagues, competitions, etc).
"""

from datetime import date, datetime
import sqlalchemy as sa
import json
from flask import render_template, flash, redirect, url_for, request, current_app, jsonify, abort
from flask_login import login_required, current_user
from flask_wtf import FlaskForm

from app import db
from app.events import bp
from app.models import Member, Pool, PoolRegistration, Booking
from app.routes import role_required
from app.events.forms import EventForm, EventSelectionForm, EventManagerAssignmentForm
from app.events.utils import (
    can_user_manage_event, get_booking_statistics, 
    create_booking_with_defaults, get_bookings_by_type
)
from app.audit import (
    audit_log_create, audit_log_update, audit_log_delete, 
    audit_log_security_event, get_model_changes
)


@bp.route('/test')
def test_route():
    """Simple test route to verify blueprint is working"""
    return "Events blueprint is working!"


@bp.route('/')
@login_required
@role_required('Event Manager')
def list_events():
    """
    List all events with filtering options.
    """
    try:
        # Get filter parameters
        event_type_filter = request.args.get('type', type=int)
        
        # Get bookings (now representing events)
        bookings = get_bookings_by_type(None)  # Get all bookings for now
        
        # In enhanced model, each booking IS an event
        events = []
        for booking in bookings:
            events.append({
                'id': booking.id,
                'name': booking.name,
                'bookings': [booking]  # Keep array structure for template compatibility
            })
        
        # Get event type options for filter
        event_types = current_app.config.get('EVENT_TYPES', {})
        
        # Calculate statistics for each event with individual error handling
        event_stats = {}
        for event in events:
            try:
                # Calculate combined stats from all bookings in this event
                event_stats[event['id']] = {
                    'total_bookings': len(event['bookings']),
                    'total_teams': sum(len(booking.teams) for booking in event['bookings']),
                    'has_pool': any(booking.pool for booking in event['bookings']),
                    'pool_members': sum(len(booking.pool.registrations) for booking in event['bookings'] if booking.pool),
                    'pool_selected': 0,  # Simplified for now
                    'pool_available': 0,  # Simplified for now
                }
            except Exception as stats_error:
                current_app.logger.error(f"Error calculating stats for event {event['id']}: {str(stats_error)}")
                # Provide safe defaults
                event_stats[event['id']] = {
                    'total_bookings': 0,
                    'total_teams': 0,
                    'has_pool': False,
                    'pool_members': 0,
                    'pool_selected': 0,
                    'pool_available': 0,
                }
        
        return render_template('list_events.html',
                             events=events,
                             event_stats=event_stats,
                             event_types=event_types,
                             current_filter=event_type_filter)
        
    except Exception as e:
        current_app.logger.error(f"Error listing events: {str(e)}")
        import traceback
        current_app.logger.error(f"Full traceback: {traceback.format_exc()}")
        flash(f'An error occurred while loading events: {str(e)}', 'error')
        return redirect(url_for('main.index'))


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required('Event Manager')
def create_event():
    """
    Create a new event.
    """
    try:
        form = EventForm()
        
        if form.validate_on_submit():
            # Create new booking (representing an event)
            # Generate a new event_id
            max_event_id = db.session.scalar(
                sa.select(sa.func.max(Booking.event_id)).where(Booking.event_id.is_not(None))
            ) or 0
            new_event_id = max_event_id + 1
            
            booking = create_booking_with_defaults(
                booking_type=form.name.data,
                event_id=new_event_id,
                gender=form.gender.data,
                format=form.format.data,
                organizer_id=current_user.id,
                booking_date=date.today(),  # Default to today
            )
            
            db.session.add(booking)
            db.session.flush()  # Get booking ID
            
            # Create pool if requested
            if form.has_pool.data:
                from app.pools.utils import create_pool_for_booking
                pool = create_pool_for_booking(booking, is_open=True)
                db.session.add(pool)
            
            db.session.commit()
            
            # Audit log
            audit_log_create('Booking', booking.id, 
                           f'Created event via booking: {booking.booking_type}',
                           {
                               'event_id': new_event_id,
                               'booking_type': booking.booking_type,
                               'format': booking.format,
                               'gender': booking.gender,
                               'has_pool': form.has_pool.data
                           })
            
            flash(f'Event "{booking.name}" created successfully!', 'success')
            return redirect(url_for('events.manage_event', event_id=new_event_id))
        
        return render_template('create_event.html', form=form)
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating event: {str(e)}")
        flash('An error occurred while creating the event.', 'error')
        return redirect(url_for('events.list_events'))


@bp.route('/manage/<int:event_id>', methods=['GET', 'POST'])
@login_required
def manage_event(event_id):
    """
    Manage a specific event.
    """
    try:
        # Get event (now represented as bookings with this event_id)
        event_bookings = db.session.scalars(
            sa.select(Booking).where(Booking.event_id == event_id)
        ).all()
        
        if not event_bookings:
            flash('Booking not found.', 'error')
            return redirect(url_for('events.list_events'))
        
        # Use the first booking to check permissions
        primary_booking = event_bookings[0]
        
        # Check permissions - Event Managers can manage all events
        if not (current_user.has_role('Event Manager') or current_user.is_admin or 
                primary_booking.organizer_id == current_user.id):
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to manage event {event_id}')
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('events.list_events'))
        
        # Get event statistics (combined from all bookings)
        booking_name = booking.name if booking else f"Booking {event_id}"
        stats = {
            'total_bookings': len(event_bookings),
            'total_teams': sum(len(booking.teams) for booking in event_bookings),
            'has_pool': any(booking.pool for booking in event_bookings),
            'pool_members': sum(len(booking.pool.registrations) for booking in event_bookings if booking.pool),
            'pool_selected': 0,  # Simplified for now
            'pool_available': 0,  # Simplified for now
        }
        
        # Get forms (populate with primary booking data)
        event_form = EventForm()
        event_form.name.data = primary_booking.booking_type
        event_form.gender.data = primary_booking.gender
        event_form.format.data = primary_booking.format
        event_form.has_pool.data = any(booking.pool for booking in event_bookings)
        
        manager_form = EventManagerAssignmentForm()
        
        # For now, use organizer as the "manager"
        if primary_booking.organizer_id:
            manager_form.event_managers.data = [primary_booking.organizer_id]
        
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'update_event' and event_form.validate_on_submit():
                # Prevent event type changes once event is created (to protect pool integrity)
                if event_form.event_type.data != event.event_type:
                    flash('Event type cannot be changed after creation to protect pool data integrity. Delete and recreate the booking if needed.', 'error')
                    return redirect(url_for('events.manage_event', event_id=booking_id))
                
                # Update event details
                old_values = {
                    'name': event.name,
                    'event_type': event.event_type,
                    'gender': event.gender,
                    'format': event.format,
                    'scoring': event.scoring,
                    'has_pool': event.has_pool
                }
                
                event.name = event_form.name.data
                # event.event_type = event_form.event_type.data  # Removed - no longer allowed
                event.gender = event_form.gender.data
                event.format = event_form.format.data
                event.scoring = event_form.scoring.data
                event.has_pool = event_form.has_pool.data
                
                db.session.commit()
                
                # Audit log changes
                changes = get_model_changes(old_values, event_form.data)
                if changes:
                    audit_log_update('Booking', booking.id, 
                                   f'Updated event: {event.name}', changes)
                
                flash('Booking updated successfully!', 'success')
                return redirect(url_for('events.manage_event', event_id=booking_id))
            
            elif action == 'update_managers' and manager_form.validate_on_submit():
                # Legacy bulk update (keeping for backwards compatibility)
                old_managers = [em.id for em in event.event_managers]
                raw_managers = request.form.getlist('event_managers')
                new_manager_ids = [int(id) for id in raw_managers] if raw_managers else []
                
                # Clear existing managers and add new ones
                event.event_managers.clear()
                if new_manager_ids:
                    new_managers = db.session.scalars(
                        sa.select(Member).where(Member.id.in_(new_manager_ids))
                    ).all()
                    event.event_managers.extend(new_managers)
                
                db.session.commit()
                
                # Audit log manager changes
                audit_log_update('Booking', booking.id, 
                               f'Updated event managers for: {event.name}',
                               {'old_managers': old_managers, 'new_managers': new_manager_ids})
                
                flash('Booking managers updated successfully!', 'success')
                return redirect(url_for('events.manage_event', event_id=booking_id))
            
            elif action == 'add_manager':
                # Add a single manager
                member_id = request.form.get('member_id')
                if member_id:
                    try:
                        member_id = int(member_id)
                        member = db.session.get(Member, member_id)
                        if member and member.status == 'Full':
                            # Check if member is not already a manager
                            if member not in event.event_managers:
                                event.event_managers.append(member)
                                db.session.commit()
                                
                                # Audit log
                                audit_log_update('Booking', booking.id, 
                                               f'Added event manager: {member.firstname} {member.lastname}',
                                               {'added_manager': member_id})
                                
                                flash(f'{member.firstname} {member.lastname} has been added as an event manager.', 'success')
                            else:
                                flash(f'{member.firstname} {member.lastname} is already an event manager.', 'warning')
                        else:
                            flash('Invalid member selected.', 'error')
                    except (ValueError, TypeError):
                        flash('Invalid member ID.', 'error')
                return redirect(url_for('events.manage_event', event_id=booking_id))
            
            elif action == 'remove_manager':
                # Remove a single manager
                member_id = request.form.get('member_id')
                if member_id:
                    try:
                        member_id = int(member_id)
                        member = db.session.get(Member, member_id)
                        if member and member in event.event_managers:
                            event.event_managers.remove(member)
                            db.session.commit()
                            
                            # Audit log
                            audit_log_update('Booking', booking.id, 
                                           f'Removed event manager: {member.firstname} {member.lastname}',
                                           {'removed_manager': member_id})
                            
                            flash(f'{member.firstname} {member.lastname} has been removed as an event manager.', 'success')
                        else:
                            flash('Manager not found or not assigned to this event.', 'error')
                    except (ValueError, TypeError):
                        flash('Invalid member ID.', 'error')
                return redirect(url_for('events.manage_event', event_id=booking_id))
        
        # Ensure manager form choices are populated before rendering
        # (in case form validation failed and choices were lost)
        if not manager_form.event_managers.choices:
            event_managers = db.session.scalars(
                sa.select(Member)
                .where(Member.status == 'Full')  # Only active/full members
                .order_by(Member.firstname, Member.lastname)
            ).all()
            manager_form.event_managers.choices = [
                (member.id, f"{member.firstname} {member.lastname}")
                for member in event_managers
            ]
        
        # Get pool information based on event type
        from app.events.utils import get_event_pool_info
        pool_info = get_event_pool_info(event)
        
        # Get bookings for this event
        event_bookings = db.session.scalars(
            sa.select(Booking).where(Booking.event_id == event_id)
            .order_by(Booking.booking_date, Booking.session)
        ).all()
        
        return render_template('manage_event.html',
                             event=event,
                             stats=stats,
                             pool_info=pool_info,
                             event_form=event_form,
                             manager_form=manager_form,
                             event_bookings=event_bookings)
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error managing event {event_id}: {str(e)}")
        flash('An error occurred while managing the event.', 'error')
        return redirect(url_for('events.list_events'))


@bp.route('/delete/<int:event_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def delete_event(event_id):
    """
    Delete an event.
    """
    try:
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('events.list_events'))
        
        booking = db.session.get(Booking, booking_id)
        if not booking:
            flash('Booking not found.', 'error')
            return redirect(url_for('events.list_events'))
        
        # Check permissions
        if not can_user_manage_event(current_user, booking):
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to delete event {event_id}')
            flash('You do not have permission to delete this event.', 'error')
            return redirect(url_for('events.list_events'))
        
        # Enhanced booking model - in the new model, we can delete bookings directly
        # No need to check for separate bookings relation
        
        booking_name = booking.name
        event_type = booking.get_event_type_name()
        
        # Delete event (cascades to pool if exists)
        db.session.delete(booking)
        db.session.commit()
        
        # Audit log
        audit_log_delete('Booking', event_id, 
                        f'Deleted event: {booking_name} ({event_type})')
        
        flash(f'Booking "{booking_name}" deleted successfully.', 'success')
        return redirect(url_for('events.list_events'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting event {event_id}: {str(e)}")
        flash('An error occurred while deleting the event.', 'error')
        return redirect(url_for('events.list_events'))


# Pool management routes (maintaining compatibility with admin routes)

@bp.route('/toggle_pool/<int:event_id>', methods=['POST'])
@login_required
def toggle_event_pool(event_id):
    """
    Toggle event pool on/off (maintains compatibility with admin routes).
    """
    try:
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('events.manage_event', event_id=booking_id))
        
        booking = db.session.get(Booking, booking_id)
        if not booking:
            flash('Booking not found.', 'error')
            return redirect(url_for('events.list_events'))
        
        # Check permissions
        if not can_user_manage_event(current_user, booking):
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to toggle pool for event {event_id}')
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('events.list_events'))
        
        # Get pool strategy for this event type
        from app.events.utils import get_event_pool_strategy, get_event_pool_info
        from app.pools.utils import create_pool_for_event, create_pool_for_booking
        
        strategy = get_event_pool_strategy(event)
        pool_info = get_event_pool_info(event)
        
        if strategy == 'none':
            flash('Pool management is not available for this event type.', 'warning')
            return redirect(url_for('events.manage_event', event_id=booking_id))
        
        old_has_pools = pool_info['has_pools']
        
        if strategy == 'event':
            # Event-level pool toggle - open/close registration instead of deleting pool
            if old_has_pools:
                if booking.pool:
                    # Toggle pool open/closed status
                    if booking.pool.is_open:
                        booking.pool.is_open = False
                        action = 'closed for registration'
                    else:
                        booking.pool.is_open = True
                        action = 'reopened for registration'
                else:
                    # Create new pool if somehow missing
                    pool = create_pool_for_event(event, is_open=True)
                    db.session.add(pool)
                    action = 'enabled and opened'
            else:
                # Enable: create event pool
                pool = create_pool_for_event(event, is_open=True)
                db.session.add(pool)
                event.has_pool = True
                action = 'enabled and opened'
                
        elif strategy == 'booking':
            # In enhanced booking model, each booking manages its own pool
            if old_has_pools:
                # Disable: remove the pool for this booking
                if booking.pool:
                    db.session.delete(booking.pool)
                booking.has_pool = False
                action = 'disabled'
            else:
                # Enable: create pool for this booking
                if not booking.pool:
                    from app.pools.utils import create_pool_for_booking
                    pool = create_pool_for_booking(booking, is_open=True)
                    db.session.add(pool)
                    booking.has_pool = True
                    action = 'enabled (pool created)'
                else:
                    action = 'enabled (pool already exists)'
        
        db.session.commit()
        
        # Audit log
        audit_log_update('Booking', booking.id, 
                        f'Pool {action} for event: {event.name} (strategy: {strategy})',
                        {'old_has_pools': old_has_pools, 'new_has_pools': not old_has_pools, 'strategy': strategy})
        
        flash(f'Pool {action} for event "{event.name}".', 'success')
        return redirect(url_for('events.manage_event', event_id=booking_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling pool for event {event_id}: {str(e)}")
        flash('An error occurred while updating the pool status.', 'error')
        return redirect(url_for('events.manage_event', event_id=booking_id))


@bp.route('/create_booking/<int:booking_id>', methods=['POST'])
@login_required
def create_booking(booking_id):
    """
    Create a new booking session for an existing event/booking.
    """
    try:
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('events.manage_event', event_id=booking_id))
        
        booking = db.session.get(Booking, booking_id)
        if not booking:
            flash('Booking not found.', 'error')
            return redirect(url_for('events.list_events'))
        
        # Check permissions
        if not can_user_manage_event(current_user, booking):
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to create booking for event {event_id}')
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('events.list_events'))
        
        # Get form data
        booking_date = datetime.strptime(request.form.get('booking_date'), '%Y-%m-%d').date()
        session = int(request.form.get('session'))
        vs = request.form.get('vs', '').strip() or None
        home_away = request.form.get('home_away', 'home')
        rink_count = int(request.form.get('rink_count', 1))
        priority = request.form.get('priority', '').strip() or None
        
        # Create booking
        booking = Booking(
            booking_date=booking_date,
            session=session,
            rink_count=rink_count,
            priority=priority,
            vs=vs,
            home_away=home_away,
            event_id=booking.id,
            booking_type='event'
        )
        
        db.session.add(booking)
        db.session.flush()  # Get booking ID
        
        # Create pool if this event uses booking-level pools
        from app.events.utils import get_event_pool_strategy
        from app.pools.utils import create_pool_for_booking
        
        strategy = get_event_pool_strategy(event)
        if strategy == 'booking':
            # Create pool for this booking
            pool = create_pool_for_booking(booking, is_open=True)
            db.session.add(pool)
        
        db.session.commit()
        
        # Audit log
        audit_log_create('Booking', booking.id, 
                        f'Created booking for event: {event.name} on {booking_date}',
                        {'event_id': booking.id, 'date': str(booking_date), 'session': session, 'strategy': strategy})
        
        flash(f'Booking created successfully for {booking_date.strftime("%B %d, %Y")}!', 'success')
        return redirect(url_for('events.manage_event', event_id=booking_id))
        
    except ValueError as e:
        flash('Invalid date format.', 'error')
        return redirect(url_for('events.manage_event', event_id=booking_id))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating booking for event {event_id}: {str(e)}")
        flash('An error occurred while creating the booking.', 'error')
        return redirect(url_for('events.manage_event', event_id=booking_id))


# API endpoints

@bp.route('/api/v1/event/<int:event_id>', methods=['GET'])
@login_required
def api_get_event(event_id):
    """
    Get event details (AJAX endpoint).
    """
    try:
        booking = db.session.get(Booking, event_id)
        if not booking:
            return jsonify({
                'success': False,
                'error': 'Booking not found'
            }), 404
        
        # Check permission
        if not can_user_manage_event(current_user, booking):
            return jsonify({
                'success': False,
                'error': 'Permission denied'
            }), 403
        
        # Get statistics
        stats = get_event_statistics(event)
        
        # Format event data
        event_data = {
            'id': booking.id,
            'name': event.name,
            'event_type': event.event_type,
            'event_type_name': booking.get_event_type_name(),
            'gender': event.gender,
            'gender_name': event.get_gender_name(),
            'format': event.format,
            'format_name': event.get_format_name(),
            'scoring': event.scoring,
            'has_pool': event.has_pool,
            'created_at': event.created_at.isoformat(),
            'statistics': stats,
            'managers': [
                {
                    'id': manager.id,
                    'name': f"{manager.firstname} {manager.lastname}"
                }
                for manager in event.event_managers
            ]
        }
        
        return jsonify({
            'success': True,
            'event': event_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting event {event_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500