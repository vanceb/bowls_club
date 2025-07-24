from flask import Blueprint

bp = Blueprint('members', __name__)

from app.members import routes