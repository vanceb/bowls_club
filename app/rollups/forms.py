"""
Rollup-specific forms.
Forms for roll-up booking functionality.
"""

from datetime import date, timedelta
from flask import current_app
from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, TextAreaField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, ValidationError


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