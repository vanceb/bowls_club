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
from app.models import Pool, PoolRegistration, Booking, Member
from app.routes import role_required
from app.pools.forms import PoolForm, PoolRegistrationForm
from app.pools.utils import (
    can_user_manage_pool, get_pool_statistics,
    create_pool_for_booking
)
from app.bookings.utils import can_user_manage_event
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
    Create a pool for an event (via Booking model).
    """
    try:
        # Check if event exists by finding its bookings
        event_booking = db.session.scalar(
            sa.select(Booking).where(Booking.event_id == event_id).limit(1)
        )
        
        # Get event name from first booking for display
        event_name = f"Event {event_id}"
        
        # Check if pool already exists for this event
        existing_pool = db.session.scalar(
            sa.select(Pool).join(Booking).where(Booking.event_id == event_id).limit(1)
        )
        if existing_pool:
            flash('Pool already exists for this event.', 'error')
            return redirect(url_for('pools.manage_pool', pool_id=existing_pool.id))
        
        form = PoolForm()
        
        if form.validate_on_submit():
            # TODO: This route needs to be updated for booking-centric system
            flash('Pool creation via event ID is temporarily disabled. Please use booking management instead.', 'error')
            return redirect(url_for('main.index'))
            # pool = create_pool_for_booking_with_event_id(
            #     event_id=event_id,
            #     max_players=form.max_players.data,
            #     auto_close_date=form.auto_close_date.data,
            #     is_open=form.is_open.data
            # )
            # 
            # db.session.add(pool)
            # db.session.commit()
            
            # # Audit log
            # audit_log_create('Pool', pool.id,
            #                f'Created event pool for event ID: {event_id}', 
            #                {
            #                    'event_id': event_id,
            #                    'max_players': pool.max_players,
            #                    'is_open': pool.is_open
            #                })
            
            # flash(f'Pool created successfully for event.', 'success')
            # return redirect(url_for('pools.manage_pool', pool_id=pool.id))
        
        return render_template('create_pool.html', 
                             form=form, 
                             event_id=event_id,
                             event_name=event_name,
                             pool_type='event')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating event pool for event {event_id}: {str(e)}")
        flash('An error occurred while creating the pool.', 'error')
        return redirect(url_for('bookings.admin_list_bookings'))


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
        # All pools are now booking-based, show all active members
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


# Admin pool management routes (migrated from admin blueprint)

@bp.route('/admin/create_event_pool/<int:event_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def admin_create_event_pool(event_id):
    """
    Create a new pool for an event (admin interface)
    """
    try:
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('events.manage_event', event_id=event_id))
        
        # Check if event already has a pool
        existing_pool = db.session.scalar(
            sa.select(Pool).join(Booking).where(Booking.event_id == event_id).limit(1)
        )
        if existing_pool:
            flash('This event already has pool registration enabled.', 'warning')
            return redirect(url_for('events.manage_event', event_id=event_id))
        
        # TODO: This route needs to be updated for booking-centric system
        flash('Pool creation via event ID is temporarily disabled. Please use booking management instead.', 'error')
        return redirect(url_for('main.index'))
        # Create new pool via booking
        # new_pool = create_pool_for_booking_with_event_id(
        #     event_id=event_id,
        #     is_open=True
        # )
        
        # db.session.add(new_pool)
        # db.session.commit()
        # 
        # # Audit log
        # audit_log_create('Pool', new_pool.id, 
        #                 f'Created pool for event ID: {event_id}')
        
        flash(f'Pool registration has been enabled for event.', 'success')
        return redirect(url_for('events.manage_event', event_id=event_id))
        
    except Exception as e:
        current_app.logger.error(f"Error creating event pool: {str(e)}")
        flash('An error occurred while creating the pool.', 'error')
        return redirect(url_for('events.manage_event', event_id=event_id))


@bp.route('/admin/add_member_to_pool/<int:event_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def admin_add_member_to_pool(event_id):
    """
    Add a member to the event pool (for Event Managers to expand the pool)
    """
    try:
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('events.manage_event', event_id=event_id))
        
        # Check if event has pool enabled
        event_pool = db.session.scalar(
            sa.select(Pool).join(Booking).where(Booking.event_id == event_id).limit(1)
        )
        if not event_pool:
            flash('This event does not have pool registration enabled.', 'error')
            return redirect(url_for('events.manage_event', event_id=event_id))
        
        # Get member_id from form
        member_id = request.form.get('member_id', type=int)
        if not member_id:
            flash('Please select a member to add.', 'error')
            return redirect(url_for('events.manage_event', event_id=event_id))
        
        # Get the member
        member = db.session.get(Member, member_id)
        if not member:
            flash('Member not found.', 'error')
            return redirect(url_for('events.manage_event', event_id=event_id))
        
        # Check if member is already in the pool
        existing_registration = db.session.scalar(
            sa.select(PoolRegistration).where(
                PoolRegistration.pool_id == event_pool.id,
                PoolRegistration.member_id == member_id
            )
        )
        if existing_registration:
            flash(f'{member.firstname} {member.lastname} is already registered for this event.', 'warning')
            return redirect(url_for('events.manage_event', event_id=event_id))
        
        # Add member to pool
        registration = PoolRegistration(
            pool_id=event_pool.id,
            member_id=member_id
        )
        db.session.add(registration)
        db.session.commit()
        
        # Audit log
        audit_log_create('PoolRegistration', registration.id, 
                        f'Event Manager added {member.firstname} {member.lastname} to pool for event ID: {event_id}')
        
        flash(f'{member.firstname} {member.lastname} added to event pool successfully!', 'success')
        return redirect(url_for('events.manage_event', event_id=event_id))
        
    except Exception as e:
        current_app.logger.error(f"Error adding member to pool: {str(e)}")
        flash('An error occurred while adding member to pool.', 'error')
        return redirect(url_for('events.manage_event', event_id=event_id))


@bp.route('/admin/delete_from_pool/<int:registration_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def admin_delete_from_pool(registration_id):
    """
    Remove a member from the event pool entirely (admin version of user withdrawal)
    """
    try:
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('bookings.admin_list_bookings'))
        
        # Get the registration
        registration = db.session.get(PoolRegistration, registration_id)
        if not registration:
            flash('Registration not found.', 'error')
            return redirect(url_for('bookings.admin_list_bookings'))
        
        # Get event info from pool's booking
        event_booking = registration.pool.booking
        event_id = event_booking.event_id if event_booking else 'unknown'
        
        # Store info for audit log and flash message
        member_name = f"{registration.member.firstname} {registration.member.lastname}"
        
        # Delete the registration entirely (same as user withdrawal)
        db.session.delete(registration)
        db.session.commit()
        
        # Audit log
        audit_log_delete('PoolRegistration', registration_id, 
                        f'Event Manager removed {member_name} from pool for event ID: {event_id}')
        
        flash(f'{member_name} removed from event pool successfully!', 'success')
        return redirect(url_for('events.manage_event', event_id=event_id))
        
    except Exception as e:
        current_app.logger.error(f"Error removing member from pool: {str(e)}")
        flash('An error occurred while removing member from pool.', 'error')
        return redirect(url_for('bookings.admin_list_bookings'))


@bp.route('/admin/auto_select_pool_members/<int:event_id>', methods=['POST'])
@login_required
@role_required('Event Manager')
def admin_auto_select_pool_members(event_id):
    """
    Automatically select pool members for team creation based on criteria
    """
    try:
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('events.manage_event', event_id=event_id))
        
        # Get event pool
        event_pool = db.session.scalar(
            sa.select(Pool).join(Booking).where(Booking.event_id == event_id).limit(1)
        )
        if not event_pool:
            flash('Event not found or pool not enabled.', 'error')
            return redirect(url_for('bookings.admin_list_bookings'))
        
        selection_method = request.form.get('method', 'oldest_first')
        num_to_select = request.form.get('count', type=int)
        
        if not num_to_select or num_to_select <= 0:
            flash('Invalid selection count.', 'error')
            return redirect(url_for('events.manage_event', event_id=event_id))
        
        # Get all registered members (all pool registrations are active)
        registered_members = list(event_pool.registrations)
        
        if len(registered_members) < num_to_select:
            flash(f'Only {len(registered_members)} registered members available, cannot select {num_to_select}.', 'warning')
            return redirect(url_for('events.manage_event', event_id=event_id))
        
        # Apply selection method
        if selection_method == 'oldest_first':
            selected_registrations = sorted(registered_members, key=lambda r: r.registered_at)[:num_to_select]
        elif selection_method == 'random':
            import random
            selected_registrations = random.sample(registered_members, num_to_select)
        else:
            # Default to oldest first
            selected_registrations = sorted(registered_members, key=lambda r: r.registered_at)[:num_to_select]
        
        # Pool status no longer tracked - all registered members are available for team creation
        flash(f'Pool members are always available for team creation. Use "Create Teams from Pool" instead.', 'info')
        return redirect(url_for('events.manage_event', event_id=event_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in auto pool selection: {str(e)}")
        flash('An error occurred during automatic selection.', 'error')
        return redirect(url_for('bookings.admin_list_bookings'))


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
        if pool.booking and pool.booking.event_id:
            pool_data['event'] = {
                'id': pool.booking.event_id,
                'name': f'Event {pool.booking.event_id}',
                'event_type': 'Event'
            }
        
        if pool.booking:
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