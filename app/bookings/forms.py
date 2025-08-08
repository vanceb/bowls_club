"""
Booking-related forms.
Forms migrated from main forms.py for booking functionality.
"""

from datetime import date, timedelta
from flask import current_app
from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, IntegerField, StringField, TextAreaField, HiddenField, SubmitField, FieldList, FormField
from wtforms.validators import DataRequired, Optional, Length, NumberRange, ValidationError


class BookingForm(FlaskForm):
    booking_date = DateField('Booking Date', validators=[DataRequired()])
    session = SelectField(
        'Session',
        coerce=int,
        choices=[],  # Choices will be populated dynamically
        validators=[DataRequired()]
    )
    rink_count = IntegerField(
        'Number of Rinks Needed',
        validators=[DataRequired()],  # NumberRange will be added dynamically
        default=1
    )
    priority = StringField('Priority', validators=[Optional(), Length(max=50)])
    vs = StringField('Opposition Team', validators=[Optional(), Length(max=128)])
    home_away = SelectField(
        'Venue',
        choices=[],  # Choices will be populated dynamically
        validators=[Optional()]
    )
    submit = SubmitField('Submit')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate the session choices dynamically from the app config
        self.session.choices = [
            (key, value) for key, value in current_app.config.get('DAILY_SESSIONS', {}).items()
        ]
        # Populate the home/away choices dynamically from the app config
        self.home_away.choices = [('', 'Select venue...')] + [
            (value, key) for key, value in current_app.config.get('HOME_AWAY_OPTIONS', {}).items()
        ]
        # Dynamically set the max value for the rink_count field
        max_rinks = int(current_app.config.get('RINKS', 6))
        self.rink_count.validators.append(NumberRange(min=1, max=max_rinks))

    def validate_rink_count(self, field):
        """
        Custom validator to check that the booking doesn't exceed available rinks
        for the given date and session.
        """
        if self.booking_date.data and self.session.data:
            from app.models import Booking
            from app import db
            from flask import current_app
            import sqlalchemy as sa
            
            # Calculate total existing bookings for this date/session
            # Exclude away games from rink availability calculations
            from app.bookings.utils import add_home_games_filter
            
            existing_query = sa.select(sa.func.sum(Booking.rink_count)).where(
                Booking.booking_date == self.booking_date.data,
                Booking.session == self.session.data
            )
            # Apply home games filter to exclude away games
            existing_query = add_home_games_filter(existing_query)
            
            existing_rinks = db.session.scalar(existing_query) or 0
            
            # Get the maximum available rinks
            max_rinks = int(current_app.config.get('RINKS', 6))
            
            # Check if this booking would exceed capacity
            if existing_rinks + field.data > max_rinks:
                available_rinks = max_rinks - existing_rinks
                if available_rinks <= 0:
                    raise ValidationError(f'No rinks available for this date and session')
                else:
                    raise ValidationError(f'Only {available_rinks} rink(s) available for this date and session')



class BookingResponseForm(FlaskForm):
    """Generic form for responding to booking invitations (rollups, events, etc.)"""
    response = SelectField(
        'Your Response',
        choices=[
            ('confirmed', 'Accept - I can play'),
            ('declined', 'Decline - Cannot play')
        ],
        validators=[DataRequired()]
    )
    submit = SubmitField('Submit Response')


# League Management Forms

class LeagueCreateForm(FlaskForm):
    """Step 1: Basic league details"""
    league_name = StringField('League Name', validators=[DataRequired(), Length(max=128)])
    format = SelectField('Format', coerce=int, choices=[], validators=[DataRequired()])
    event_type = HiddenField('Event Type', default=3)  # Fixed to League
    gender = SelectField('Gender', coerce=int, choices=[], validators=[DataRequired()])
    submit = SubmitField('Next: Schedule Games')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Populate format choices from config
        self.format.choices = [
            (value, key) for key, value in current_app.config.get('EVENT_FORMATS', {}).items()
        ]
        
        # Event type is fixed to League (ID 3) - set the data value
        self.event_type.data = 3
        
        # Populate gender choices from config
        self.gender.choices = [
            (value, key) for key, value in current_app.config.get('EVENT_GENDERS', {}).items()
        ]


class GameScheduleRowForm(FlaskForm):
    """Individual game in the league schedule table"""
    date = DateField('Date', validators=[Optional()])
    session = SelectField('Session', coerce=int, choices=[], validators=[Optional()])
    venue = SelectField('Venue', choices=[
        ('home', 'Home'),
        ('away', 'Away'),
        ('neutral', 'Neutral')
    ], validators=[Optional()], default='home')
    opponent = StringField('Opponent', validators=[Optional(), Length(max=128)])
    notes = StringField('Notes', validators=[Optional(), Length(max=255)])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate session choices from config
        self.session.choices = [(0, 'Select session...')] + [
            (key, value) for key, value in current_app.config.get('DAILY_SESSIONS', {}).items()
        ]


class LeagueScheduleForm(FlaskForm):
    """Step 2: Schedule league games in table format"""
    games = FieldList(FormField(GameScheduleRowForm), min_entries=1)
    
    # Action buttons
    add_row = SubmitField('Add Row')
    create_all = SubmitField('Create All Games')
    cancel = SubmitField('Cancel')
    
    def validate_games(self, field):
        """Validate that at least one game has a date and no duplicate dates"""
        valid_games = [game for game in field.data if game.get('date')]
        
        if not valid_games:
            raise ValidationError('Please schedule at least one game.')
        
        # Check for duplicate dates
        dates_seen = set()
        for game in valid_games:
            game_date = game.get('date')
            if game_date in dates_seen:
                raise ValidationError(f'Duplicate date found: {game_date.strftime("%Y-%m-%d")}')
            dates_seen.add(game_date)