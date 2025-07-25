from flask import Blueprint

bp = Blueprint('content', __name__, template_folder='templates')

from app.content import routes