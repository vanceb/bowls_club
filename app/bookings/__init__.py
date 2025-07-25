from flask import Blueprint

bp = Blueprint('bookings', __name__, template_folder='templates')

from app.bookings import routes