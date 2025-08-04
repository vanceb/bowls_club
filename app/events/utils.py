"""
Utility functions for event management.
"""

from typing import Optional, Dict, Any
from flask import current_app
import sqlalchemy as sa

from app import db
from app.models import Member, Booking


def get_event_type_blueprint(event_type: int) -> str:
    """
    Determine which blueprint should handle a specific event type.
    
    Args:
        event_type: Integer event type from EVENT_TYPES config
        
    Returns:
        Blueprint name to handle this event type
    """
    # Map event types to their specialized blueprints
    # When we create specialized blueprints, update this mapping
    blueprint_mapping = {
        3: 'leagues',      # League events
        2: 'competitions', # Competition events  
        1: 'events',       # Social events (use base events)
        4: 'events',       # Friendly events (use base events)
        5: 'rollups',      # Roll Up events (existing rollups blueprint)
        6: 'events',       # Other events (use base events)
    }
    
    return blueprint_mapping.get(event_type, 'events')


def get_available_positions_for_booking(booking: Booking) -> list[str]:
    """
    Get available team positions for a booking based on its format.
    
    Args:
        booking: Booking model instance
        
    Returns:
        List of position names for this booking format
    """
    if not booking or not booking.format:
        return ['Player']
    
    team_positions_config = current_app.config.get('TEAM_POSITIONS', {})
    return team_positions_config.get(booking.format, ['Player'])


def can_user_manage_booking(user: Member, booking: Booking) -> bool:
    """
    Check if a user can manage a specific booking.
    
    Args:
        user: Member instance
        booking: Booking instance
        
    Returns:
        True if user can manage the booking
    """
    # Admins can manage all bookings
    if user.is_admin:
        return True
    
    # Event Manager role can manage all bookings
    if user.has_role('Event Manager'):
        return True
    
    # Check if user is the organizer of this booking
    return booking.organizer_id == user.id if booking.organizer_id else False


def get_booking_statistics(booking: Booking) -> Dict[str, Any]:
    """
    Get statistics for a booking.
    
    Args:
        booking: Booking instance
        
    Returns:
        Dictionary with booking statistics
    """
    stats = {
        'total_teams': len(booking.teams) if booking.teams else 0,
        'has_pool': booking.pool is not None,
        'pool_members': 0,
        'pool_selected': 0,
        'pool_available': 0,
    }
    
    # Calculate pool statistics if pool exists
    if booking.pool:
        try:
            # Use PoolRegistration model
            from app.models import PoolRegistration
            pool_registrations = db.session.scalars(
                sa.select(PoolRegistration).where(PoolRegistration.pool_id == booking.pool.id)
            ).all()
            
            stats['pool_members'] = len(pool_registrations)
            stats['pool_selected'] = sum(1 for pr in pool_registrations if pr.status == 'selected')
            stats['pool_available'] = sum(1 for pr in pool_registrations if pr.status in ['registered'])
        except Exception:
            # Fallback to basic pool info
            stats['pool_members'] = 0
    
    return stats


def create_booking_with_defaults(booking_type: str, **kwargs) -> Booking:
    """
    Create a new booking with sensible defaults.
    
    Args:
        booking_type: Booking type string
        **kwargs: Additional booking attributes
        
    Returns:
        New Booking instance (not yet committed to database)
    """
    defaults = {
        'gender': 4,  # Open gender by default
        'format': 5,  # Fours - 2 Wood by default
        'session': 'All Day',
    }
    
    # Merge defaults with provided kwargs
    booking_data = {**defaults, **kwargs}
    booking_data['booking_type'] = booking_type
    
    return Booking(**booking_data)


def get_bookings_by_type(booking_type: Optional[str] = None) -> list[Booking]:
    """
    Get bookings, optionally filtered by type.
    
    Args:
        booking_type: Optional booking type to filter by
        
    Returns:
        List of Booking instances
    """
    query = sa.select(Booking).order_by(Booking.booking_date.desc())
    
    if booking_type is not None:
        query = query.where(Booking.booking_type == booking_type)
    
    return db.session.scalars(query).all()


def get_recent_bookings(limit: int = 10) -> list[Booking]:
    """
    Get recently created bookings.
    
    Args:
        limit: Maximum number of bookings to return
        
    Returns:
        List of recent Booking instances
    """
    return db.session.scalars(
        sa.select(Booking)
        .order_by(Booking.created_at.desc())
        .limit(limit)
    ).all()


def get_booking_pool_strategy(booking: Booking) -> str:
    """
    Get the pool attachment strategy for a booking based on its type.
    
    Args:
        booking: Booking instance
        
    Returns:
        'booking' or 'none'
    """
    # Bookings can have pools attached directly
    return 'booking' if booking.booking_type != 'Private' else 'none'


def get_booking_pool_info(booking: Booking) -> dict:
    """
    Get pool information for a booking.
    
    Args:
        booking: Booking instance
        
    Returns:
        Dictionary with pool information
    """
    strategy = get_booking_pool_strategy(booking)
    
    info = {
        'strategy': strategy,
        'has_pools': False,
        'pools': [],
        'total_members': 0,
        'can_toggle_pools': True,
        'pool_status': 'no_pool'
    }
    
    if strategy == 'none':
        info['can_toggle_pools'] = False
        return info
    
    # Booking-level pool
    if booking.pool:
        info['has_pools'] = True
        info['pools'] = [booking.pool]
        info['total_members'] = len(booking.pool.registrations)
        info['pool_status'] = 'open' if booking.pool.is_open else 'closed'
    else:
        info['pool_status'] = 'no_pool'
    
    return info


def booking_has_pool(booking: Booking) -> bool:
    """
    Check if a booking has a pool.
    
    Args:
        booking: Booking instance
        
    Returns:
        True if booking has a pool
    """
    return get_booking_pool_info(booking)['has_pools']


def booking_pool_member_count(booking: Booking) -> int:
    """
    Get total number of members in a booking's pool.
    
    Args:
        booking: Booking instance
        
    Returns:
        Pool member count
    """
    return get_booking_pool_info(booking)['total_members']


# Backward compatibility functions for existing code
def can_user_manage_event(user: Member, event_or_booking) -> bool:
    """
    Backward compatibility function for can_user_manage_event.
    
    Args:
        user: Member instance
        event_or_booking: Booking instance (previously Event)
        
    Returns:
        True if user can manage the booking
    """
    return can_user_manage_booking(user, event_or_booking)