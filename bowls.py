import sqlalchemy as sa
import sqlalchemy.orm as so
from app import create_app, db
from app.models import Member, Booking, Event, Role, Post, PolicyPage, BookingTeam, TeamMember
import os

app = create_app(os.getenv('FLASK_CONFIG') or 'development')

@app.shell_context_processor
def make_shell_context():
    return {
        'sa': sa, 
        'so': so, 
        'db': db, 
        'Member': Member, 
        'Booking': Booking, 
        'Event': Event,
        'Role': Role,
        'Post': Post,
        'PolicyPage': PolicyPage,
        'BookingTeam': BookingTeam,
        'TeamMember': TeamMember
    }

if __name__ == '__main__':
    app.run(debug=True)