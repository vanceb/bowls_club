"""
Booking-related forms.
Forms migrated from main forms.py for booking functionality.
"""

from datetime import date, timedelta
from flask import current_app
from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, IntegerField, StringField, TextAreaField, HiddenField, SubmitField
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


class RollUpBookingForm(FlaskForm):
    """Form for creating roll-up bookings"""
    booking_date = DateField('Date', validators=[DataRequired()])
    session = SelectField(
        'Session',
        coerce=int,
        choices=[],  # Choices will be populated dynamically
        validators=[DataRequired()]
    )
    organizer_notes = TextAreaField(
        'Notes (optional)', 
        validators=[Optional(), Length(max=500)],
        render_kw={'placeholder': 'Optional notes about the roll-up...', 'rows': 3}
    )
    invited_players = HiddenField('Invite Players')
    submit = SubmitField('Create Roll-Up')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Populate the session choices dynamically from the app config
        self.session.choices = [
            (key, value) for key, value in current_app.config.get('DAILY_SESSIONS', {}).items()
        ]

    def validate_booking_date(self, field):
        """Validate that the booking date is within the allowed advance booking period"""
        if not field.data:
            return
            
        today = date.today()
        max_advance_days = current_app.config.get('ROLLUP_ADVANCE_BOOKING_DAYS', 7)
        max_date = today + timedelta(days=max_advance_days)
        
        if field.data < today:
            raise ValidationError('Roll-up bookings cannot be made for past dates')
        
        if field.data > max_date:
            raise ValidationError(f'Roll-up bookings can only be made {max_advance_days} days in advance')

    def validate_invited_players(self, field):
        """Validate invited players count"""
        if not field.data:
            return
            
        max_players = current_app.config.get('ROLLUP_MAX_PLAYERS', 8)
        
        # Parse comma-separated string of player IDs
        try:
            player_ids = [int(x.strip()) for x in field.data.split(',') if x.strip()]
        except ValueError:
            raise ValidationError('Invalid player selection format')
        
        if len(player_ids) > max_players:
            raise ValidationError(f'Maximum {max_players} players allowed per roll-up')
        
        if len(player_ids) == 0:
            raise ValidationError('At least one player must be invited to the roll-up')