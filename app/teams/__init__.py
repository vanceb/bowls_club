from flask import Blueprint

bp = Blueprint('teams', __name__, template_folder='templates')

from app.teams import routes