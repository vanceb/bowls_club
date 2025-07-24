from flask import Blueprint

bp = Blueprint('members', __name__, template_folder='templates')

from app.members import routes