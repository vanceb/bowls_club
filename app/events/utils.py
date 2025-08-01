"""
Utility functions for event management.
"""

from typing import Optional, Dict, Any
from flask import current_app
import sqlalchemy as sa

from app import db
from app.models import Event, Member


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


def get_available_positions_for_event(event: Event) -> list[str]:
    """
    Get available team positions for an event based on its format.
    
    Args:
        event: Event model instance
        
    Returns:
        List of position names for this event format
    """
    if not event or not event.format:
        return ['Player']
    
    team_positions_config = current_app.config.get('TEAM_POSITIONS', {})
    return team_positions_config.get(event.format, ['Player'])


def can_user_manage_event(user: Member, event: Event) -> bool:
    """
    Check if a user can manage a specific event.
    
    Args:
        user: Member instance
        event: Event instance
        
    Returns:
        True if user can manage the event
    """
    # Admins can manage all events
    if user.is_admin:
        return True
    
    # Event Manager role can manage all events
    if user.has_role('Event Manager'):
        return True
    
    # Check if user is specifically assigned as event manager for this event
    return user in event.event_managers


def get_event_statistics(event: Event) -> Dict[str, Any]:
    """
    Get statistics for an event.
    
    Args:
        event: Event instance
        
    Returns:
        Dictionary with event statistics
    """
    stats = {
        'total_bookings': len(event.bookings) if event.bookings else 0,
        'total_teams': sum(len(booking.teams) for booking in event.bookings) if event.bookings else 0,
        'has_pool': event.has_pool_enabled() if hasattr(event, 'has_pool_enabled') else event.has_pool,
        'pool_members': 0,
        'pool_selected': 0,
        'pool_available': 0,
    }
    
    # Calculate pool statistics if pool exists (regardless of enabled status)
    if hasattr(event, 'pool') and event.pool:
        try:
            # Use PoolRegistration model instead of generic "members"
            from app.models import PoolRegistration
            pool_registrations = db.session.scalars(
                sa.select(PoolRegistration).where(PoolRegistration.pool_id == event.pool.id)
            ).all()
            
            stats['pool_members'] = len(pool_registrations)
            stats['pool_selected'] = sum(1 for pr in pool_registrations if pr.status == 'selected')
            stats['pool_available'] = sum(1 for pr in pool_registrations if pr.status in ['registered'])
        except Exception:
            # Fallback to basic pool info
            stats['pool_members'] = 0
    
    return stats


def create_event_with_defaults(name: str, event_type: int, **kwargs) -> Event:
    """
    Create a new event with sensible defaults.
    
    Args:
        name: Event name
        event_type: Event type integer
        **kwargs: Additional event attributes
        
    Returns:
        New Event instance (not yet committed to database)
    """
    defaults = {
        'gender': 4,  # Open gender by default
        'format': 5,  # Fours - 2 Wood by default
        'has_pool': False,
    }
    
    # Merge defaults with provided kwargs
    event_data = {**defaults, **kwargs}
    event_data['name'] = name
    event_data['event_type'] = event_type
    
    return Event(**event_data)


def get_events_by_type(event_type: Optional[int] = None) -> list[Event]:
    """
    Get events, optionally filtered by type.
    
    Args:
        event_type: Optional event type to filter by
        
    Returns:
        List of Event instances
    """
    query = sa.select(Event).order_by(Event.name)
    
    if event_type is not None:
        query = query.where(Event.event_type == event_type)
    
    return db.session.scalars(query).all()


def get_recent_events(limit: int = 10) -> list[Event]:
    """
    Get recently created events.
    
    Args:
        limit: Maximum number of events to return
        
    Returns:
        List of recent Event instances
    """
    return db.session.scalars(
        sa.select(Event)
        .order_by(Event.created_at.desc())
        .limit(limit)
    ).all()


def get_event_pool_strategy(event: Event) -> str:
    """
    Get the pool attachment strategy for an event based on its type.
    
    Args:
        event: Event instance
        
    Returns:
        'event', 'booking', or 'none'
    """
    pool_strategy_config = current_app.config.get('EVENT_POOL_STRATEGY', {})
    return pool_strategy_config.get(event.event_type, 'event')


def get_event_pool_info(event: Event) -> dict:
    """
    Get pool information for an event, handling both event-level and booking-level pools.
    
    Args:
        event: Event instance
        
    Returns:
        Dictionary with pool information
    """
    strategy = get_event_pool_strategy(event)
    
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
    
    if strategy == 'event':
        # Event-level pool
        if event.pool:
            info['has_pools'] = True
            info['pools'] = [event.pool]
            info['total_members'] = len(event.pool.registrations)
            info['pool_status'] = 'open' if event.pool.is_open else 'closed'
        else:
            info['pool_status'] = 'no_pool'
            
    elif strategy == 'booking':
        # Booking-level pools
        pools = []
        total_members = 0
        has_open_pools = False
        has_closed_pools = False
        
        for booking in event.bookings:
            if booking.pool:
                pools.append(booking.pool)
                total_members += len(booking.pool.registrations)
                if booking.pool.is_open:
                    has_open_pools = True
                else:
                    has_closed_pools = True
        
        info['has_pools'] = len(pools) > 0
        info['pools'] = pools
        info['total_members'] = total_members
        
        # Determine overall pool status
        if not pools:
            info['pool_status'] = 'no_pool'
        elif has_open_pools and has_closed_pools:
            info['pool_status'] = 'mixed'
        elif has_open_pools:
            info['pool_status'] = 'open'
        else:
            info['pool_status'] = 'closed'
    
    return info


def event_has_any_pools(event: Event) -> bool:
    """
    Check if an event has any pools (event-level or booking-level).
    
    Args:
        event: Event instance
        
    Returns:
        True if event has any pools
    """
    return get_event_pool_info(event)['has_pools']


def event_pool_member_count(event: Event) -> int:
    """
    Get total number of members across all pools for an event.
    
    Args:
        event: Event instance
        
    Returns:
        Total member count
    """
    return get_event_pool_info(event)['total_members']