"""
Booking-related utility functions.
Utilities migrated from main utils.py for booking functionality.
Includes essential functions moved from events/utils.py during blueprint consolidation.
"""

from typing import Optional, Dict, Any
from flask import current_app
import sqlalchemy as sa

from app import db
from app.models import Member, Booking


def add_home_games_filter(query):
    """
    Add a filter to a SQLAlchemy query to exclude away games from bookings.
    
    This utility function centralizes the logic for filtering out away games
    from booking queries used in calendar display and rink availability calculations.
    
    Args:
        query: SQLAlchemy query object that includes Booking model
        
    Returns:
        Modified query with home games filter applied
    """
    return query.where(sa.or_(Booking.home_away != 'away', Booking.home_away == None))


# Functions moved from events/utils.py during blueprint consolidation

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


def create_booking_with_defaults(name: str, **kwargs) -> Booking:
    """
    Create a new booking with sensible defaults.
    
    Args:
        name: Event name
        **kwargs: Additional booking attributes
        
    Returns:
        New Booking instance (not yet committed to database)
    """
    from datetime import date
    
    defaults = {
        'booking_type': 'event',  # Default booking type
        'gender': 4,  # Open gender by default
        'format': 5,  # Fours - 2 Wood by default
        'event_type': 1,  # Default to Social event type
        'session': 1,  # Default to first session (integer)
        'rink_count': 1,  # Default rink count
        'booking_date': date.today(),  # Default to today
        'has_pool': False,  # Default no pool
        'series_commitment_required': False,  # Default no series commitment
    }
    
    # Merge defaults with provided kwargs
    booking_data = {**defaults, **kwargs}
    booking_data['name'] = name
    
    return Booking(**booking_data)


def format_booking_details(booking: Booking, include_date: bool = True, rollup_include_date: bool = None) -> str:
    """
    Generate consistent booking details string for display across the application.
    
    Format: 
    - Regular events: "Event Name vs Opposition (🏠 Home) - Sep 03, 2025"
    - Roll-ups: "Creator Name - 04 Aug 2025 - 10:00am - 1:00pm"
    
    Args:
        booking: Booking instance
        include_date: Whether to include the booking date for regular events (default: True)
        rollup_include_date: Whether to include date for roll-ups (defaults to include_date if None)
        
    Returns:
        Formatted booking details string with HTML for icons
    """
    from flask import current_app
    
    # Handle roll-ups differently
    if booking.booking_type == 'rollup':
        details = f"{booking.organizer.firstname} {booking.organizer.lastname}"
        
        # Use rollup_include_date if specified, otherwise fall back to include_date
        show_rollup_date = rollup_include_date if rollup_include_date is not None else include_date
        
        if show_rollup_date and booking.booking_date:
            details += f" - {booking.booking_date.strftime('%d %b %Y')}"
        
        # Add session time
        sessions = current_app.config.get('DAILY_SESSIONS', {})
        session_time = sessions.get(booking.session, f'Session {booking.session}')
        details += f" - {session_time}"
        
        return details
    
    # Regular event formatting
    # Start with event name
    details = booking.name
    
    # Add opposition if present
    if booking.vs:
        details += f" vs {booking.vs}"
    
    # Add venue with icon if present
    if booking.home_away:
        is_away = booking.home_away == 'away'
        icon = '<i class="fas fa-plane"></i>' if is_away else '<i class="fas fa-home"></i>'
        details += f" ({icon} {booking.home_away.title()})"
    
    # Add date if requested
    if include_date and booking.booking_date:
        details += f" - {booking.booking_date.strftime('%b %d, %Y')}"
    
    return details


def get_bookings_by_type(booking_type: Optional[str] = None) -> list[Booking]:
    """
    Get bookings filtered by type.
    
    Args:
        booking_type: Optional booking type filter
        
    Returns:
        List of bookings
    """
    query = sa.select(Booking).order_by(Booking.booking_date.desc())
    
    if booking_type:
        query = query.where(Booking.booking_type == booking_type)
    
    return db.session.scalars(query).all()


# Pool Strategy Functions

def get_pool_strategy_for_booking(booking: Booking) -> str:
    """
    Get the pool strategy for a booking based on its event type.
    
    Args:
        booking: Booking instance
        
    Returns:
        Pool strategy: 'booking', 'event', or 'none'
    """
    event_pool_strategy = current_app.config.get('EVENT_POOL_STRATEGY', {})
    return event_pool_strategy.get(booking.event_type, 'booking')


def get_primary_booking_in_series(series_id: str) -> Optional[Booking]:
    """
    Get the primary booking in a series (earliest by date).
    The primary booking is the one that owns the shared pool for 'event' strategy.
    
    Args:
        series_id: The series ID to search for
        
    Returns:
        Primary Booking instance or None if series not found
    """
    if not series_id:
        return None
        
    return db.session.scalar(
        sa.select(Booking)
        .where(Booking.series_id == series_id)
        .order_by(Booking.booking_date.asc(), Booking.id.asc())
        .limit(1)
    )


def should_create_pool_for_duplication(original_booking: Booking, duplicate_booking: Booking) -> tuple[bool, Optional[str]]:
    """
    Determine whether to create a new pool for a duplicated booking based on EVENT_POOL_STRATEGY.
    
    Args:
        original_booking: The booking being duplicated
        duplicate_booking: The new duplicate booking
        
    Returns:
        Tuple of (should_create_new_pool, reason)
        - should_create_new_pool: True if a new pool should be created
        - reason: String explaining the decision for logging
    """
    # If original doesn't have a pool, no pool needed
    if not original_booking.has_pool or not original_booking.pool:
        return False, "Original booking has no pool"
    
    strategy = get_pool_strategy_for_booking(original_booking)
    
    if strategy == 'none':
        return False, f"Strategy '{strategy}' - no pool should be created"
    
    elif strategy == 'booking':
        return True, f"Strategy '{strategy}' - create new pool per booking"
    
    elif strategy == 'event':
        # For event strategy, don't create new pool - will reference primary booking's pool
        return False, f"Strategy '{strategy}' - will share pool with primary booking in series"
    
    else:
        # Unknown strategy, default to booking-level
        current_app.logger.warning(f"Unknown pool strategy '{strategy}' for event type {original_booking.event_type}, defaulting to 'booking'")
        return True, f"Unknown strategy '{strategy}' - defaulting to create new pool"


def get_effective_pool_for_booking(booking: Booking) -> Optional['Pool']:
    """
    Get the effective pool for a booking, considering pool strategy.
    For 'event' strategy, this may return the primary booking's pool.
    
    Args:
        booking: The booking to get the pool for
        
    Returns:
        Pool instance or None
    """
    # If booking has its own pool, return it
    if booking.pool:
        return booking.pool
    
    # If no series, no shared pool possible
    if not booking.series_id:
        return None
    
    strategy = get_pool_strategy_for_booking(booking)
    
    # Only 'event' strategy allows sharing pools
    if strategy != 'event':
        return None
    
    # Find the primary booking in the series
    primary_booking = get_primary_booking_in_series(booking.series_id)
    if primary_booking and primary_booking.id != booking.id:
        return primary_booking.pool
    
    return None


# Legacy function for backward compatibility - will be removed
def can_user_manage_event(user: Member, event_or_booking) -> bool:
    """
    Legacy function for backward compatibility.
    Use can_user_manage_booking instead.
    """
    current_app.logger.warning("can_user_manage_event is deprecated, use can_user_manage_booking instead")
    
    # If it's a booking object, use the new function
    if hasattr(event_or_booking, 'booking_date'):
        return can_user_manage_booking(user, event_or_booking)
    
    # Legacy behavior for any remaining event objects
    return user.is_admin or user.has_role('Event Manager')