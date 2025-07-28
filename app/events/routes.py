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
from app.models import Event, Member, EventPool, PoolRegistration
from app.routes import role_required
from app.events.forms import EventForm, EventSelectionForm, EventManagerAssignmentForm
from app.events.utils import (
    can_user_manage_event, get_event_statistics, 
    create_event_with_defaults, get_events_by_type
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
        
        # Get events
        events = get_events_by_type(event_type_filter)
        
        # Get event type options for filter
        event_types = current_app.config.get('EVENT_TYPES', {})
        
        # Calculate statistics for each event with individual error handling
        event_stats = {}
        for event in events:
            try:
                event_stats[event.id] = get_event_statistics(event)
            except Exception as stats_error:
                current_app.logger.error(f"Error calculating stats for event {event.id}: {str(stats_error)}")
                # Provide safe defaults
                event_stats[event.id] = {
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
            # Create new event
            event = create_event_with_defaults(
                name=form.name.data,
                event_type=form.event_type.data,
                gender=form.gender.data,
                format=form.format.data,
                scoring=form.scoring.data,
                has_pool=form.has_pool.data
            )
            
            db.session.add(event)
            db.session.flush()  # Get event ID
            
            # Add current user as event manager
            event.event_managers.append(current_user)
            
            db.session.commit()
            
            # Audit log
            audit_log_create('Event', event.id, 
                           f'Created event: {event.name} ({event.get_event_type_name()})',
                           {
                               'event_type': event.get_event_type_name(),
                               'format': event.get_format_name(),
                               'gender': event.get_gender_name(),
                               'has_pool': event.has_pool
                           })
            
            flash(f'Event "{event.name}" created successfully!', 'success')
            return redirect(url_for('events.manage_event', event_id=event.id))
        
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
        event = db.session.get(Event, event_id)
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('events.list_events'))
        
        # Check permissions
        if not can_user_manage_event(current_user, event):
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to manage event {event_id}')
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('events.list_events'))
        
        # Get event statistics
        stats = get_event_statistics(event)
        
        # Get forms
        event_form = EventForm(obj=event)
        manager_form = EventManagerAssignmentForm()
        
        # Pre-populate manager form
        manager_form.event_managers.data = [em.id for em in event.event_managers]
        
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'update_event' and event_form.validate_on_submit():
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
                event.event_type = event_form.event_type.data
                event.gender = event_form.gender.data
                event.format = event_form.format.data
                event.scoring = event_form.scoring.data
                event.has_pool = event_form.has_pool.data
                
                db.session.commit()
                
                # Audit log changes
                changes = get_model_changes(old_values, event_form.data)
                if changes:
                    audit_log_update('Event', event.id, 
                                   f'Updated event: {event.name}', changes)
                
                flash('Event updated successfully!', 'success')
                return redirect(url_for('events.manage_event', event_id=event_id))
            
            elif action == 'update_managers' and manager_form.validate_on_submit():
                # Update event managers
                old_managers = [em.id for em in event.event_managers]
                new_manager_ids = manager_form.event_managers.data or []
                
                # Clear existing managers and add new ones
                event.event_managers.clear()
                if new_manager_ids:
                    new_managers = db.session.scalars(
                        sa.select(Member).where(Member.id.in_(new_manager_ids))
                    ).all()
                    event.event_managers.extend(new_managers)
                
                db.session.commit()
                
                # Audit log manager changes
                audit_log_update('Event', event.id, 
                               f'Updated event managers for: {event.name}',
                               {'old_managers': old_managers, 'new_managers': new_manager_ids})
                
                flash('Event managers updated successfully!', 'success')
                return redirect(url_for('events.manage_event', event_id=event_id))
        
        return render_template('manage_event.html',
                             event=event,
                             stats=stats,
                             event_form=event_form,
                             manager_form=manager_form)
        
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
        
        event = db.session.get(Event, event_id)
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('events.list_events'))
        
        # Check permissions
        if not can_user_manage_event(current_user, event):
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to delete event {event_id}')
            flash('You do not have permission to delete this event.', 'error')
            return redirect(url_for('events.list_events'))
        
        # Check if event has bookings
        if event.bookings:
            flash('Cannot delete event with existing bookings. Please remove all bookings first.', 'error')
            return redirect(url_for('events.manage_event', event_id=event_id))
        
        event_name = event.name
        event_type = event.get_event_type_name()
        
        # Delete event (cascades to pool if exists)
        db.session.delete(event)
        db.session.commit()
        
        # Audit log
        audit_log_delete('Event', event_id, 
                        f'Deleted event: {event_name} ({event_type})')
        
        flash(f'Event "{event_name}" deleted successfully.', 'success')
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
            return redirect(url_for('events.manage_event', event_id=event_id))
        
        event = db.session.get(Event, event_id)
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('events.list_events'))
        
        # Check permissions
        if not can_user_manage_event(current_user, event):
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to toggle pool for event {event_id}')
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('events.list_events'))
        
        old_status = event.has_pool
        event.has_pool = not event.has_pool
        
        # If enabling pool and none exists, create it
        if event.has_pool and not event.pool:
            pool = EventPool(
                event_id=event.id,
                is_open=True,
                max_players=None  # No limit by default
            )
            db.session.add(pool)
        
        db.session.commit()
        
        # Audit log
        action = 'enabled' if event.has_pool else 'disabled'
        audit_log_update('Event', event.id, 
                        f'Pool {action} for event: {event.name}',
                        {'old_pool_status': old_status, 'new_pool_status': event.has_pool})
        
        flash(f'Pool {action} for event "{event.name}".', 'success')
        return redirect(url_for('events.manage_event', event_id=event_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling pool for event {event_id}: {str(e)}")
        flash('An error occurred while updating the pool status.', 'error')
        return redirect(url_for('events.manage_event', event_id=event_id))


# API endpoints

@bp.route('/api/v1/event/<int:event_id>', methods=['GET'])
@login_required
def api_get_event(event_id):
    """
    Get event details (AJAX endpoint).
    """
    try:
        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({
                'success': False,
                'error': 'Event not found'
            }), 404
        
        # Check permission
        if not can_user_manage_event(current_user, event):
            return jsonify({
                'success': False,
                'error': 'Permission denied'
            }), 403
        
        # Get statistics
        stats = get_event_statistics(event)
        
        # Format event data
        event_data = {
            'id': event.id,
            'name': event.name,
            'event_type': event.event_type,
            'event_type_name': event.get_event_type_name(),
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