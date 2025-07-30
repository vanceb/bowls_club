"""
Pool management utility functions.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from flask import current_app
import sqlalchemy as sa

from app import db
from app.models import Pool, PoolRegistration, Event, Booking, Member


def can_user_manage_pool(user: Member, pool: Pool) -> bool:
    """
    Check if a user can manage a specific pool.
    
    Args:
        user: The user to check permissions for
        pool: The pool to check permissions for
        
    Returns:
        True if user can manage the pool, False otherwise
    """
    if not user or not user.is_authenticated:
        return False
    
    # Admin users can manage all pools
    if user.has_role('Admin'):
        return True
    
    # Event Managers can manage all pools
    if user.has_role('Event Manager'):
        return True
    
    # If pool is associated with an event, check if user is an event manager for that event
    if pool.event:
        return user in pool.event.event_managers
    
    # If pool is associated with a booking, check if user is the organizer (for roll-ups)
    if pool.booking and pool.booking.organizer_id:
        return user.id == pool.booking.organizer_id
    
    return False


def get_pool_statistics(pool: Pool) -> Dict[str, Any]:
    """
    Get comprehensive statistics for a pool.
    
    Args:
        pool: The pool to get statistics for
        
    Returns:
        Dictionary containing pool statistics
    """
    try:
        registrations = pool.registrations
        
        # Basic counts
        total_registered = len(registrations)
        registered_count = len([r for r in registrations if r.status == 'registered'])
        selected_count = len([r for r in registrations if r.status == 'selected'])
        declined_count = len([r for r in registrations if r.status == 'declined'])
        available_count = registered_count + selected_count  # Available for selection
        
        # Capacity information
        capacity = pool.max_players
        is_full = pool.is_full() if capacity else False
        capacity_percentage = (total_registered / capacity * 100) if capacity else 0
        
        # Status information
        is_open = pool.is_open
        can_register = pool.can_register()
        
        # Time-based information
        created_at = pool.created_at
        closed_at = pool.closed_at
        auto_close_date = pool.auto_close_date
        will_auto_close = auto_close_date and auto_close_date > datetime.now() if auto_close_date else False
        
        # Pool type specific information
        pool_context = {}
        if pool.event:
            pool_context.update({
                'event_name': pool.event.name,
                'event_type': pool.event.get_event_type_name(),
                'event_format': pool.event.get_format_name(),
                'event_has_bookings': len(pool.event.bookings) > 0
            })
        elif pool.booking:
            pool_context.update({
                'booking_date': pool.booking.booking_date,
                'booking_session': pool.booking.session,
                'booking_type': pool.booking.booking_type,
                'has_organizer': pool.booking.organizer_id is not None
            })
        
        return {
            # Basic counts
            'total_registered': total_registered,
            'registered_count': registered_count,
            'selected_count': selected_count,
            'declined_count': declined_count,
            'available_count': available_count,
            
            # Capacity
            'capacity': capacity,
            'is_full': is_full,
            'capacity_percentage': round(capacity_percentage, 1),
            'remaining_spots': (capacity - total_registered) if capacity else None,
            
            # Status
            'is_open': is_open,
            'can_register': can_register,
            'pool_type': pool.pool_type,
            'pool_name': pool.pool_name,
            
            # Timing
            'created_at': created_at,
            'closed_at': closed_at,
            'auto_close_date': auto_close_date,
            'will_auto_close': will_auto_close,
            
            # Context
            **pool_context
        }
        
    except Exception as e:
        current_app.logger.error(f"Error calculating pool statistics for pool {pool.id}: {str(e)}")
        # Return safe defaults
        return {
            'total_registered': 0,
            'registered_count': 0,
            'selected_count': 0,
            'declined_count': 0,
            'available_count': 0,
            'capacity': pool.max_players,
            'is_full': False,
            'capacity_percentage': 0,
            'remaining_spots': pool.max_players,
            'is_open': pool.is_open,
            'can_register': False,
            'pool_type': pool.pool_type,
            'pool_name': pool.pool_name,
            'created_at': pool.created_at,
            'closed_at': pool.closed_at,
            'auto_close_date': pool.auto_close_date,
            'will_auto_close': False
        }


def create_pool_for_event(event: Event, max_players: Optional[int] = None, 
                         auto_close_date: Optional[datetime] = None,
                         is_open: bool = True) -> Pool:
    """
    Create a new pool associated with an event.
    
    Args:
        event: The event to associate the pool with
        max_players: Maximum number of players (None for unlimited)
        auto_close_date: Date to automatically close the pool
        is_open: Whether the pool starts open for registration
        
    Returns:
        New Pool instance (not yet committed to database)
    """
    pool = Pool(
        event_id=event.id,
        booking_id=None,
        is_open=is_open,
        max_players=max_players,
        auto_close_date=auto_close_date
    )
    
    # Update event's has_pool flag
    event.has_pool = True
    
    return pool


def create_pool_for_booking(booking: Booking, max_players: Optional[int] = None,
                           auto_close_date: Optional[datetime] = None,
                           is_open: bool = True) -> Pool:
    """
    Create a new pool associated with a booking.
    
    Args:
        booking: The booking to associate the pool with
        max_players: Maximum number of players (None for unlimited)
        auto_close_date: Date to automatically close the pool
        is_open: Whether the pool starts open for registration
        
    Returns:
        New Pool instance (not yet committed to database)
    """
    pool = Pool(
        event_id=None,
        booking_id=booking.id,
        is_open=is_open,
        max_players=max_players,
        auto_close_date=auto_close_date
    )
    
    return pool


def get_available_members_for_pool(pool: Pool) -> list[Member]:
    """
    Get list of members who can be added to a pool.
    
    Args:
        pool: The pool to check for
        
    Returns:
        List of Member objects not already in the pool
    """
    # Get all registered member IDs for this pool
    registered_member_ids = [reg.member_id for reg in pool.registrations]
    
    # Get all active members not in the pool
    query = sa.select(Member).where(
        Member.status == 'Active',
        ~Member.id.in_(registered_member_ids) if registered_member_ids else True
    ).order_by(Member.firstname, Member.lastname)
    
    return db.session.scalars(query).all()


def get_pools_for_user(user: Member, include_managed: bool = True, 
                      include_registered: bool = True) -> list[Pool]:
    """
    Get pools relevant to a specific user.
    
    Args:
        user: The user to get pools for
        include_managed: Include pools the user can manage
        include_registered: Include pools the user is registered for
        
    Returns:
        List of Pool objects
    """
    pool_ids = set()
    
    if include_managed:
        # Pools for events the user manages
        if user.has_role('Event Manager') or user.has_role('Admin'):
            # All pools
            all_pools = db.session.scalars(sa.select(Pool)).all()
            pool_ids.update(pool.id for pool in all_pools)
        else:
            # Only pools for events they manage
            managed_event_pools = db.session.scalars(
                sa.select(Pool).join(Event).where(
                    Event.event_managers.contains(user)
                )
            ).all()
            pool_ids.update(pool.id for pool in managed_event_pools)
            
            # Pools for bookings they organize
            organized_booking_pools = db.session.scalars(
                sa.select(Pool).join(Booking).where(
                    Booking.organizer_id == user.id
                )
            ).all()
            pool_ids.update(pool.id for pool in organized_booking_pools)
    
    if include_registered:
        # Pools the user is registered for
        registered_pools = db.session.scalars(
            sa.select(Pool).join(PoolRegistration).where(
                PoolRegistration.member_id == user.id
            )
        ).all()
        pool_ids.update(pool.id for pool in registered_pools)
    
    if not pool_ids:
        return []
    
    # Get the actual pool objects
    pools = db.session.scalars(
        sa.select(Pool).where(Pool.id.in_(pool_ids))
        .order_by(Pool.created_at.desc())
    ).all()
    
    return pools


def auto_close_expired_pools():
    """
    Automatically close pools that have passed their auto_close_date.
    This should be called periodically (e.g., via a scheduled task).
    """
    try:
        now = datetime.now()
        expired_pools = db.session.scalars(
            sa.select(Pool).where(
                Pool.is_open == True,
                Pool.auto_close_date.is_not(None),
                Pool.auto_close_date <= now
            )
        ).all()
        
        closed_count = 0
        for pool in expired_pools:
            pool.close_pool()
            closed_count += 1
            current_app.logger.info(f"Auto-closed expired pool {pool.id}: {pool.pool_name}")
        
        if closed_count > 0:
            db.session.commit()
            current_app.logger.info(f"Auto-closed {closed_count} expired pools")
        
        return closed_count
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error auto-closing expired pools: {str(e)}")
        return 0


def get_pool_registration_summary(pool: Pool) -> Dict[str, Any]:
    """
    Get a summary of pool registrations suitable for display.
    
    Args:
        pool: The pool to summarize
        
    Returns:
        Dictionary with registration summary data
    """
    registrations = pool.registrations
    
    # Group by status
    by_status = {}
    for reg in registrations:
        status = reg.status
        if status not in by_status:
            by_status[status] = []
        by_status[status].append({
            'id': reg.id,
            'member_id': reg.member_id,
            'member_name': f"{reg.member.firstname} {reg.member.lastname}",
            'registered_at': reg.registered_at,
            'last_updated': reg.last_updated
        })
    
    # Sort each status group by member name
    for status in by_status:
        by_status[status].sort(key=lambda x: x['member_name'])
    
    return {
        'total_count': len(registrations),
        'by_status': by_status,
        'status_counts': {
            status: len(members) for status, members in by_status.items()
        }
    }