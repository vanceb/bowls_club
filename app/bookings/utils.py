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