"""
Pool management routes.

This module provides routes for managing pools that can be associated with:
- Events (event-level pools for tournaments, competitions)  
- Bookings (booking-level pools for individual matches)
"""

from datetime import datetime
import sqlalchemy as sa
from flask import render_template, flash, redirect, url_for, request, current_app, jsonify, abort
from flask_login import login_required, current_user
from flask_wtf import FlaskForm

from app import db
from app.pools import bp
from app.models import Pool, PoolRegistration, Event, Booking, Member
from app.routes import role_required
from app.pools.forms import PoolForm, PoolRegistrationForm
from app.pools.utils import (
    can_user_manage_pool, get_pool_statistics,
    create_pool_for_event, create_pool_for_booking
)
from app.events.utils import can_user_manage_event
from app.audit import (
    audit_log_create, audit_log_update, audit_log_delete,
    audit_log_security_event, get_model_changes
)


@bp.route('/test')
def test_route():
    """Simple test route to verify blueprint is working"""
    return "Pools blueprint is working!"


@bp.route('/')
@login_required
@role_required('Event Manager')
def list_pools():
    """
    List all pools with filtering options.
    """
    try:
        # Get filter parameters
        pool_type_filter = request.args.get('type')  # 'event' or 'booking'
        
        # Build query
        query = sa.select(Pool)
        
        if pool_type_filter == 'event':
            query = query.where(Pool.event_id.is_not(None))
        elif pool_type_filter == 'booking':
            query = query.where(Pool.booking_id.is_not(None))
        
        pools = db.session.scalars(query.order_by(Pool.created_at.desc())).all()
        
        # Calculate statistics for each pool
        pool_stats = {}
        for pool in pools:
            try:
                pool_stats[pool.id] = get_pool_statistics(pool)
            except Exception as stats_error:
                current_app.logger.error(f"Error calculating stats for pool {pool.id}: {str(stats_error)}")
                pool_stats[pool.id] = {
                    'registered_count': 0,
                    'selected_count': 0,
                    'available_count': 0,
                    'capacity': pool.max_players
                }
        
        return render_template('list_pools.html',
                             pools=pools,
                             pool_stats=pool_stats,
                             current_filter=pool_type_filter)
        
    except Exception as e:
        current_app.logger.error(f"Error listing pools: {str(e)}")
        flash(f'An error occurred while loading pools: {str(e)}', 'error')
        return redirect(url_for('main.index'))


@bp.route('/create/event/<int:event_id>', methods=['GET', 'POST'])
@login_required
@role_required('Event Manager')
def create_event_pool(event_id):
    """
    Create a pool for an event.
    """
    try:
        event = db.session.get(Event, event_id)
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('events.list_events'))
        
        # Check permissions - must be able to manage this specific event
        if not can_user_manage_event(current_user, event):
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to create pool for event {event_id}')
            flash('You do not have permission to manage this event.', 'error')
            return redirect(url_for('events.list_events'))
        
        # Check if pool already exists
        if event.pool:
            flash('Pool already exists for this event.', 'error')
            return redirect(url_for('pools.manage_pool', pool_id=event.pool.id))
        
        form = PoolForm()
        
        if form.validate_on_submit():
            pool = create_pool_for_event(
                event=event,
                max_players=form.max_players.data,
                auto_close_date=form.auto_close_date.data,
                is_open=form.is_open.data
            )
            
            db.session.add(pool)
            db.session.commit()
            
            # Audit log
            audit_log_create('Pool', pool.id,
                           f'Created event pool for: {event.name}', 
                           {
                               'event_id': event.id,
                               'max_players': pool.max_players,
                               'is_open': pool.is_open
                           })
            
            flash(f'Pool created successfully for event "{event.name}".', 'success')
            return redirect(url_for('pools.manage_pool', pool_id=pool.id))
        
        return render_template('create_pool.html', 
                             form=form, 
                             event=event,
                             pool_type='event')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating event pool for event {event_id}: {str(e)}")
        flash('An error occurred while creating the pool.', 'error')
        return redirect(url_for('events.list_events'))


@bp.route('/create/booking/<int:booking_id>', methods=['GET', 'POST'])
@login_required
@role_required('Event Manager')
def create_booking_pool(booking_id):
    """
    Create a pool for a booking.
    """
    try:
        booking = db.session.get(Booking, booking_id)
        if not booking:
            flash('Booking not found.', 'error')
            return redirect(url_for('bookings.bookings'))
        
        # Check if pool already exists
        if booking.pool:
            flash('Pool already exists for this booking.', 'error')
            return redirect(url_for('pools.manage_pool', pool_id=booking.pool.id))
        
        form = PoolForm()
        
        if form.validate_on_submit():
            pool = create_pool_for_booking(
                booking=booking,
                max_players=form.max_players.data,
                auto_close_date=form.auto_close_date.data,
                is_open=form.is_open.data
            )
            
            db.session.add(pool)
            db.session.commit()
            
            # Audit log
            audit_log_create('Pool', pool.id,
                           f'Created booking pool for: {booking.booking_date}',
                           {
                               'booking_id': booking.id,
                               'max_players': pool.max_players,
                               'is_open': pool.is_open
                           })
            
            flash(f'Pool created successfully for booking on {booking.booking_date}.', 'success')
            return redirect(url_for('pools.manage_pool', pool_id=pool.id))
        
        return render_template('create_pool.html',
                             form=form,
                             booking=booking,
                             pool_type='booking')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating booking pool for booking {booking_id}: {str(e)}")
        flash('An error occurred while creating the pool.', 'error')
        return redirect(url_for('bookings.bookings'))


@bp.route('/manage/<int:pool_id>', methods=['GET', 'POST'])
@login_required
def manage_pool(pool_id):
    """
    Manage a specific pool.
    """
    try:
        pool = db.session.get(Pool, pool_id)
        if not pool:
            flash('Pool not found.', 'error')
            return redirect(url_for('pools.list_pools'))
        
        # Check permissions
        if not can_user_manage_pool(current_user, pool):
            audit_log_security_event('ACCESS_DENIED',
                                   f'Unauthorized attempt to manage pool {pool_id}')
            flash('You do not have permission to manage this pool.', 'error')
            return redirect(url_for('pools.list_pools'))
        
        # Get pool statistics
        stats = get_pool_statistics(pool)
        
        # Get forms
        pool_form = PoolForm(obj=pool)
        registration_form = PoolRegistrationForm()
        
        # Pre-populate registration form with available members
        if pool.event:
            # For event pools, show all active members
            available_members = db.session.scalars(
                sa.select(Member).where(Member.status == 'Active')
            ).all()
        else:
            # For booking pools, show all active members
            available_members = db.session.scalars(
                sa.select(Member).where(Member.status == 'Active')
            ).all()
        
        registration_form.member_id.choices = [
            (member.id, f"{member.firstname} {member.lastname}")
            for member in available_members
            if not pool.is_member_registered(member.id)
        ]
        
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'update_pool' and pool_form.validate_on_submit():
                # Update pool details
                old_values = {
                    'max_players': pool.max_players,
                    'auto_close_date': pool.auto_close_date,
                    'is_open': pool.is_open
                }
                
                pool.max_players = pool_form.max_players.data
                pool.auto_close_date = pool_form.auto_close_date.data
                pool.is_open = pool_form.is_open.data
                
                db.session.commit()
                
                # Audit log changes
                changes = get_model_changes(old_values, pool_form.data)
                if changes:
                    audit_log_update('Pool', pool.id,
                                   f'Updated pool: {pool.pool_name}', changes)
                
                flash('Pool updated successfully!', 'success')
                return redirect(url_for('pools.manage_pool', pool_id=pool_id))
            
            elif action == 'add_member' and registration_form.validate_on_submit():
                # Add member to pool
                member_id = registration_form.member_id.data
                
                if pool.is_member_registered(member_id):
                    flash('Member is already registered in this pool.', 'error')
                else:
                    registration = PoolRegistration(
                        pool_id=pool.id,
                        member_id=member_id,
                        status='registered'
                    )
                    db.session.add(registration)
                    db.session.commit()
                    
                    member = db.session.get(Member, member_id)
                    audit_log_create('PoolRegistration', registration.id,
                                   f'Added {member.firstname} {member.lastname} to pool: {pool.pool_name}')
                    
                    flash(f'Member added to pool successfully.', 'success')
                
                return redirect(url_for('pools.manage_pool', pool_id=pool_id))
        
        return render_template('manage_pool.html',
                             pool=pool,
                             stats=stats,
                             pool_form=pool_form,
                             registration_form=registration_form)
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error managing pool {pool_id}: {str(e)}")
        flash('An error occurred while managing the pool.', 'error')
        return redirect(url_for('pools.list_pools'))


@bp.route('/toggle/<int:pool_id>', methods=['POST'])
@login_required
def toggle_pool_status(pool_id):
    """
    Toggle pool open/closed status.
    """
    try:
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('pools.manage_pool', pool_id=pool_id))
        
        pool = db.session.get(Pool, pool_id)
        if not pool:
            flash('Pool not found.', 'error')
            return redirect(url_for('pools.list_pools'))
        
        # Check permissions
        if not can_user_manage_pool(current_user, pool):
            audit_log_security_event('ACCESS_DENIED',
                                   f'Unauthorized attempt to toggle pool {pool_id}')
            flash('You do not have permission to manage this pool.', 'error')
            return redirect(url_for('pools.list_pools'))
        
        old_status = pool.is_open
        if pool.is_open:
            pool.close_pool()
        else:
            pool.reopen_pool()
        
        db.session.commit()
        
        # Audit log
        action = 'closed' if old_status else 'opened'
        audit_log_update('Pool', pool.id,
                        f'Pool {action}: {pool.pool_name}',
                        {'old_status': old_status, 'new_status': pool.is_open})
        
        flash(f'Pool {action} successfully.', 'success')
        return redirect(url_for('pools.manage_pool', pool_id=pool_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling pool {pool_id}: {str(e)}")
        flash('An error occurred while updating the pool status.', 'error')
        return redirect(url_for('pools.manage_pool', pool_id=pool_id))


@bp.route('/register/<int:pool_id>', methods=['POST'])
@login_required
def register_member(pool_id):
    """
    Register current user to a pool (self-registration).
    """
    try:
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('pools.list_pools'))
        
        pool = db.session.get(Pool, pool_id)
        if not pool:
            flash('Pool not found.', 'error')
            return redirect(url_for('pools.list_pools'))
        
        if not pool.can_register():
            flash('Pool is not accepting new registrations.', 'error')
            return redirect(url_for('pools.list_pools'))
        
        if pool.is_member_registered(current_user.id):
            flash('You are already registered for this pool.', 'error')
            return redirect(url_for('pools.list_pools'))
        
        registration = PoolRegistration(
            pool_id=pool.id,
            member_id=current_user.id,
            status='registered'
        )
        db.session.add(registration)
        db.session.commit()
        
        audit_log_create('PoolRegistration', registration.id,
                        f'Self-registered for pool: {pool.pool_name}')
        
        flash('Successfully registered for the pool!', 'success')
        return redirect(url_for('pools.list_pools'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error registering for pool {pool_id}: {str(e)}")
        flash('An error occurred while registering for the pool.', 'error')
        return redirect(url_for('pools.list_pools'))


@bp.route('/unregister/<int:registration_id>', methods=['POST'])
@login_required
def unregister_member(registration_id):
    """
    Remove a member from a pool.
    """
    try:
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('pools.list_pools'))
        
        registration = db.session.get(PoolRegistration, registration_id)
        if not registration:
            flash('Registration not found.', 'error')
            return redirect(url_for('pools.list_pools'))
        
        pool = registration.pool
        
        # Check permissions - either the member themselves or pool manager
        if (current_user.id != registration.member_id and 
            not can_user_manage_pool(current_user, pool)):
            audit_log_security_event('ACCESS_DENIED',
                                   f'Unauthorized attempt to remove registration {registration_id}')
            flash('You do not have permission to remove this registration.', 'error')
            return redirect(url_for('pools.list_pools'))
        
        member_name = f"{registration.member.firstname} {registration.member.lastname}"
        pool_name = pool.pool_name
        
        db.session.delete(registration)
        db.session.commit()
        
        audit_log_delete('PoolRegistration', registration_id,
                        f'Removed {member_name} from pool: {pool_name}')
        
        flash(f'Member removed from pool successfully.', 'success')
        
        # Redirect based on permissions
        if can_user_manage_pool(current_user, pool):
            return redirect(url_for('pools.manage_pool', pool_id=pool.id))
        else:
            return redirect(url_for('pools.list_pools'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error removing registration {registration_id}: {str(e)}")
        flash('An error occurred while removing the registration.', 'error')
        return redirect(url_for('pools.list_pools'))


@bp.route('/delete/<int:pool_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def delete_pool(pool_id):
    """
    Delete a pool.
    """
    try:
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('pools.list_pools'))
        
        pool = db.session.get(Pool, pool_id)
        if not pool:
            flash('Pool not found.', 'error')
            return redirect(url_for('pools.list_pools'))
        
        # Check permissions
        if not can_user_manage_pool(current_user, pool):
            audit_log_security_event('ACCESS_DENIED',
                                   f'Unauthorized attempt to delete pool {pool_id}')
            flash('You do not have permission to delete this pool.', 'error')
            return redirect(url_for('pools.list_pools'))
        
        pool_name = pool.pool_name
        pool_type = pool.pool_type
        
        # Delete pool (cascades to registrations)
        db.session.delete(pool)
        db.session.commit()
        
        # Audit log
        audit_log_delete('Pool', pool_id, f'Deleted pool: {pool_name}')
        
        flash(f'Pool "{pool_name}" deleted successfully.', 'success')
        return redirect(url_for('pools.list_pools'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting pool {pool_id}: {str(e)}")
        flash('An error occurred while deleting the pool.', 'error')
        return redirect(url_for('pools.list_pools'))


# API endpoints

@bp.route('/api/v1/pool/<int:pool_id>', methods=['GET'])
@login_required
def api_get_pool(pool_id):
    """
    Get pool details (AJAX endpoint).
    """
    try:
        pool = db.session.get(Pool, pool_id)
        if not pool:
            return jsonify({
                'success': False,
                'error': 'Pool not found'
            }), 404
        
        # Check permission
        if not can_user_manage_pool(current_user, pool):
            return jsonify({
                'success': False,
                'error': 'Permission denied'
            }), 403
        
        # Get statistics
        stats = get_pool_statistics(pool)
        
        # Format pool data
        pool_data = {
            'id': pool.id,
            'pool_type': pool.pool_type,
            'pool_name': pool.pool_name,
            'is_open': pool.is_open,
            'max_players': pool.max_players,
            'auto_close_date': pool.auto_close_date.isoformat() if pool.auto_close_date else None,
            'created_at': pool.created_at.isoformat(),
            'closed_at': pool.closed_at.isoformat() if pool.closed_at else None,
            'statistics': stats,
            'registrations': [
                {
                    'id': reg.id,
                    'member_id': reg.member_id,
                    'member_name': f"{reg.member.firstname} {reg.member.lastname}",
                    'registered_at': reg.registered_at.isoformat(),
                    'status': reg.status
                }
                for reg in pool.registrations
            ]
        }
        
        # Add association details
        if pool.event:
            pool_data['event'] = {
                'id': pool.event.id,
                'name': pool.event.name,
                'event_type': pool.event.get_event_type_name()
            }
        elif pool.booking:
            pool_data['booking'] = {
                'id': pool.booking.id,
                'booking_date': pool.booking.booking_date.isoformat(),
                'session': pool.booking.session
            }
        
        return jsonify({
            'success': True,
            'pool': pool_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting pool {pool_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500