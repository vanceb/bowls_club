"""
Booking-related utility functions.
Utilities migrated from main utils.py for booking functionality.
"""

import sqlalchemy as sa


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
    from app.models import Booking
    return query.where(sa.or_(Booking.home_away != 'away', Booking.home_away == None))