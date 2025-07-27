from flask import Blueprint

bp = Blueprint('rollups', __name__, template_folder='templates')

from app.rollups import routes