# Standard library imports
from datetime import date, timedelta

# Third-party imports
import sqlalchemy as sa
from flask import current_app
from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField, SelectField, 
    HiddenField, SelectMultipleField, TextAreaField, DateField, IntegerField, FileField
)
from wtforms.widgets import CheckboxInput, ListWidget
from wtforms.validators import (
    ValidationError, DataRequired, Email, EqualTo, Length, Optional, NumberRange
)
import re

# Local application imports
from app import db
from app.models import Member, Event

# Custom password validator for complexity requirements
class PasswordComplexity:
    """
    Custom WTForms validator for password complexity requirements.
    Requires at least 8 characters with uppercase, lowercase, number, and special character.
    """
    def __init__(self, message=None):
        self.message = message or (
            'Password must be at least 8 characters long and contain: '
            'uppercase letter, lowercase letter, number, and special character (!@#$%^&*)'
        )
    
    def __call__(self, form, field):
        password = field.data
        if not password:
            return  # Let DataRequired handle empty passwords
        
        if len(password) < 8:
            raise ValidationError('Password must be at least 8 characters long')
        
        # Check for uppercase letter
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Password must contain at least one uppercase letter')
        
        # Check for lowercase letter
        if not re.search(r'[a-z]', password):
            raise ValidationError('Password must contain at least one lowercase letter')
        
        # Check for digit
        if not re.search(r'\d', password):
            raise ValidationError('Password must contain at least one number')
        
        # Check for special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError('Password must contain at least one special character (!@#$%^&*)')
        
        # Check for common weak patterns
        if re.search(r'(.)\1{2,}', password):  # Same character repeated 3+ times
            raise ValidationError('Password cannot contain the same character repeated more than twice')
        
        # Check for sequential patterns
        sequences = ['123456789', 'abcdefghijklmnopqrstuvwxyz', 'qwertyuiop']
        for seq in sequences:
            if any(seq[i:i+4] in password.lower() for i in range(len(seq)-3)):
                raise ValidationError('Password cannot contain sequential patterns')
        
        # Check for common weak passwords
        common_weak = ['password', 'Password', 'PASSWORD', '12345678', 'qwerty123']
        if password.lower() in [weak.lower() for weak in common_weak]:
            raise ValidationError('Password is too common. Please choose a stronger password')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class MemberForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=1, max=64)])
    firstname = StringField('First Name', validators=[DataRequired(), Length(min=1, max=64)])
    lastname = StringField('Last Name', validators=[DataRequired(), Length(min=1, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone Number', validators=[Optional(), Length(max=15)])
    password = PasswordField('Password', validators=[DataRequired(message="A password is required"), PasswordComplexity(), EqualTo('password2', "Passwords must match.")])
    password2 = PasswordField('Repeat Password', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], default='Male')  # New field
    # Privacy settings
    share_email = BooleanField('Share email with other members', default=True)
    share_phone = BooleanField('Share phone number with other members', default=True)
    submit = SubmitField('Apply')

    def validate_username(self, username):
        user = db.session.scalar(sa.select(Member).where(
            Member.username == username.data))
        if user is not None:
            raise ValidationError('That username is not available. Please use a different username.')

    def validate_email(self, email):
        user = db.session.scalar(sa.select(Member).where(
            Member.email == email.data))
        if user is not None:
            raise ValidationError('Please use a different email address.')

class EditMemberForm(FlaskForm):
    member_id = HiddenField()
    username = StringField('Username', validators=[DataRequired(), Length(min=1, max=64)])
    firstname = StringField('First Name', validators=[DataRequired(), Length(min=1, max=64)])
    lastname = StringField('Last Name', validators=[DataRequired(), Length(min=1, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone Number', validators=[Optional(), Length(max=15)])
    is_admin = BooleanField('Is Admin')
    gender = SelectField('Gender', choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')])
    status = SelectField(
        'Status',
        choices=[
            ('Pending', 'Pending'),
            ('Full', 'Full'),
            ('Social', 'Social'),
            ('Suspended', 'Suspended'),
            ('Life', 'Life')
        ]
    )
    # Add roles field
    roles = SelectMultipleField(
        'Roles',
        coerce=int,  # Ensure role IDs are converted to integers
        option_widget=CheckboxInput(),
        widget=ListWidget(prefix_label=False)
    )
    # Privacy settings
    share_email = BooleanField('Share email with other members', default=True)
    share_phone = BooleanField('Share phone number with other members', default=True)
    # Security settings
    lockout = BooleanField('Lock out user (prevent login)', default=False)
    submit_update = SubmitField('Update')
    submit_delete = SubmitField('Delete')

        
class RequestResetForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), PasswordComplexity()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')


class PasswordChangeForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    password = PasswordField('New Password', validators=[DataRequired(), PasswordComplexity()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Change Password')





class EditProfileForm(FlaskForm):
    firstname = StringField('First Name', validators=[DataRequired(), Length(min=1, max=64)])
    lastname = StringField('Last Name', validators=[DataRequired(), Length(min=1, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone Number', validators=[Optional(), Length(max=15)])
    gender = SelectField('Gender', choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')])
    # Privacy settings
    share_email = BooleanField('Share email with other members', default=True)
    share_phone = BooleanField('Share phone number with other members', default=True)
    submit = SubmitField('Update Profile')

    def __init__(self, original_email, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        self.original_email = original_email

    def validate_email(self, email):
        if email.data != self.original_email:
            user = db.session.scalar(sa.select(Member).where(Member.email == email.data))
            if user is not None:
                raise ValidationError('Please use a different email address.')


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
            from app.utils import add_home_games_filter
            availability_query = sa.select(sa.func.sum(Booking.rink_count)).where(
                Booking.booking_date == self.booking_date.data,
                Booking.session == self.session.data
            )
            availability_query = add_home_games_filter(availability_query)
            existing_bookings = db.session.scalar(availability_query) or 0
            
            total_rinks = int(current_app.config.get('RINKS', 6))
            available_rinks = total_rinks - existing_bookings
            
            if field.data > available_rinks:
                raise ValidationError(
                    f'Only {available_rinks} rinks available for this date/session. '
                    f'You requested {field.data} rinks.'
                )


class EventForm(FlaskForm):
    event_id = HiddenField('Event ID')
    name = StringField('Event Name', validators=[DataRequired(), Length(min=1, max=256)])
    event_type = SelectField(
        'Event Type',
        coerce=int,
        choices=[],  # Choices will be populated dynamically
        validators=[DataRequired()]
    )
    gender = SelectField(
        'Gender',
        coerce=int,
        choices=[],  # Choices will be populated dynamically
        validators=[DataRequired()]
    )
    format = SelectField(
        'Format',
        coerce=int,
        choices=[],  # Choices will be populated dynamically
        validators=[DataRequired()]
    )
    scoring = StringField('Scoring', validators=[Optional(), Length(max=64)])
    event_managers = SelectMultipleField(
        'Event Managers',
        coerce=int,
        choices=[],  # Choices will be populated dynamically
        validators=[Optional()],
        option_widget=CheckboxInput(),
        widget=ListWidget(prefix_label=False)
    )
    submit = SubmitField('Save Event')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate the event type choices dynamically from the app config
        event_types = current_app.config.get('EVENT_TYPES', {})
        self.event_type.choices = [
            (value, name) for name, value in event_types.items()
        ]
        
        # Populate the gender choices dynamically from the app config
        event_genders = current_app.config.get('EVENT_GENDERS', {})
        self.gender.choices = [
            (value, name) for name, value in event_genders.items()
        ]
        
        # Populate the format choices dynamically from the app config
        event_formats = current_app.config.get('EVENT_FORMATS', {})
        self.format.choices = [
            (value, name) for name, value in event_formats.items()
        ]
        
        # Populate the event managers choices dynamically from Members with Event Manager role
        from app.models import Member, Role
        from app import db
        import sqlalchemy as sa
        
        # Get Members who have the Event Manager role
        event_managers = db.session.scalars(
            sa.select(Member)
            .join(Member.roles)
            .where(Role.name == 'Event Manager')
            .order_by(Member.firstname, Member.lastname)
        ).all()
        
        self.event_managers.choices = [
            (manager.id, f"{manager.firstname} {manager.lastname}") for manager in event_managers
        ]


class EventSelectionForm(FlaskForm):
    selected_event = SelectField(
        'Select Event',
        coerce=int,
        choices=[],  # Choices will be populated dynamically
        validators=[Optional()]
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate the event choices dynamically from the database
        from app.models import Event
        from app import db
        import sqlalchemy as sa
        
        events = db.session.scalars(sa.select(Event).order_by(Event.name)).all()
        self.selected_event.choices = [(0, 'Create New Event')] + [
            (event.id, event.name) for event in events
        ]


class AddTeamForm(FlaskForm):
    """Form for adding a new team to an event"""
    team_name = StringField(
        'Team Name', 
        validators=[DataRequired(), Length(min=1, max=100)],
        render_kw={'placeholder': 'Enter team name (e.g. "The Misfits", "Team Alpha")'} 
    )
    submit = SubmitField('Add Team')


def create_team_member_form(event_format, event=None):
    """Factory function to create a TeamMemberForm with dynamic fields"""
    
    class TeamMemberForm(FlaskForm):
        team_id = HiddenField('Team ID')
        team_name = StringField('Team Name', validators=[DataRequired(), Length(min=1, max=100)])
        submit = SubmitField('Save Team')
    
    if event_format:
        from flask import current_app
        team_positions = current_app.config.get('TEAM_POSITIONS', {})
        positions = team_positions.get(event_format, [])
        
        # Get members for selection - prefer pool members if event is provided
        from app.models import Member
        from app import db
        import sqlalchemy as sa
        
        if event and event.has_pool_enabled() and event.pool:
            # Get all pool members (all registrations are active)
            from app.models import PoolRegistration
            pool_members = db.session.scalars(
                sa.select(Member)
                .join(PoolRegistration, Member.id == PoolRegistration.member_id)
                .where(PoolRegistration.pool_id == event.pool.id)
                .order_by(Member.firstname, Member.lastname)
            ).all()
            members = pool_members
        else:
            # Fallback to all active members
            members = db.session.scalars(
                sa.select(Member)
                .where(Member.status.in_(['Full', 'Social', 'Life']))
                .order_by(Member.firstname, Member.lastname)
            ).all()
        
        member_choices = [(0, 'Select a player...')] + [
            (member.id, f"{member.firstname} {member.lastname}") for member in members
        ]
        
        # Dynamically create fields for each position
        for position in positions:
            field_name = f"position_{position.lower().replace(' ', '_')}"
            field = SelectField(
                f"{position}",
                coerce=int,
                choices=member_choices,
                validators=[Optional()]
            )
            setattr(TeamMemberForm, field_name, field)
    
    return TeamMemberForm


class ImportUsersForm(FlaskForm):
    """Form for importing users from CSV file"""
    csv_file = FileField('CSV File', validators=[DataRequired()])
    submit = SubmitField('Import Users')


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
            invited_count = len(player_ids)
        except (ValueError, AttributeError):
            invited_count = 0
        
        # Include organizer in count (+1)
        total_players = invited_count + 1
        
        if total_players > max_players:
            raise ValidationError(f'Maximum {max_players} players allowed (including organizer). You have invited {invited_count} players.')

    def validate_session(self, field):
        """Validate session and check rink availability"""
        if not self.booking_date.data or not field.data:
            return
            
        from app.models import Booking
        from app import db
        from app.utils import add_home_games_filter
        import sqlalchemy as sa
        
        # Calculate existing bookings for this date/session
        availability_query = sa.select(sa.func.sum(Booking.rink_count)).where(
            Booking.booking_date == self.booking_date.data,
            Booking.session == field.data
        )
        availability_query = add_home_games_filter(availability_query)
        existing_bookings = db.session.scalar(availability_query) or 0
        
        total_rinks = int(current_app.config.get('RINKS', 6))
        available_rinks = total_rinks - existing_bookings
        
        if available_rinks < 1:
            raise ValidationError(f'No rinks available for this date/session. All {total_rinks} rinks are booked.')


class RollUpResponseForm(FlaskForm):
    """Form for responding to roll-up invitations"""
    response = SelectField(
        'Your Response',
        choices=[
            ('confirmed', 'Accept - I can play'),
            ('declined', 'Decline - Cannot play')
        ],
        validators=[DataRequired()]
    )
    submit = SubmitField('Submit Response')