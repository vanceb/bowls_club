"""
Pools blueprint for managing member registration pools.

This blueprint provides functionality for pools that can be associated with:
- Events (event-level pools for tournaments, competitions)
- Bookings (booking-level pools for individual matches)

The blueprint handles pool creation, member registration, status management,
and team generation from pool members.
"""

from flask import Blueprint

bp = Blueprint('pools', __name__, url_prefix='/pools', template_folder='templates')

from app.pools import routes