"""
Events blueprint for managing events across the bowls club application.

This blueprint provides base functionality for all event types:
- Event creation and management
- Integration with bookings and teams
- Event pool management
- Common utilities and forms

Specialized event types (leagues, competitions) will extend this base functionality.
"""

from flask import Blueprint

bp = Blueprint('events', __name__, url_prefix='/events', template_folder='templates')

from app.events import routes