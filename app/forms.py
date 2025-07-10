# Standard library imports
from datetime import date, timedelta

# Third-party imports
import sqlalchemy as sa
from flask import current_app
from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField, SelectField, 
    HiddenField, SelectMultipleField, TextAreaField, DateField, IntegerField
)
from wtforms.widgets import CheckboxInput, ListWidget
from wtforms.validators import (
    ValidationError, DataRequired, Email, EqualTo, Length, Optional, NumberRange
)

# Local application imports
from app import db
from app.models import Member

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class MemberForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(max=64)])
    firstname = StringField('First Name', validators=[DataRequired(), Length(max=64)])
    lastname = StringField('Last Name', validators=[DataRequired(), Length(max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone Number', validators=[Optional(), Length(max=15)])
    password = PasswordField('Password', validators=[DataRequired(message="A password is required"), Length(min=8, message="Password must be at least 8 characters long"), EqualTo('password2', "Passwords must match.")])
    password2 = PasswordField('Repeat Password', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], default='Male')  # New field
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
    username = StringField('Username', validators=[DataRequired(), Length(max=64)])
    firstname = StringField('First Name', validators=[DataRequired(), Length(max=64)])
    lastname = StringField('Last Name', validators=[DataRequired(), Length(max=64)])
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
    submit_update = SubmitField('Update')
    submit_delete = SubmitField('Delete')

        
class RequestResetForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')

class WritePostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=255)])
    summary = TextAreaField('Summary', validators=[DataRequired(), Length(max=255)])
    publish_on = DateField('Publish On', default=date.today, validators=[DataRequired()])
    expires_on = DateField(
        'Expires On',
        default=lambda: date.today() + timedelta(days=current_app.config.get('POST_EXPIRATION_DAYS', 30)),
        validators=[DataRequired()]
    )
    pin_until = DateField('Pin Until', validators=[Optional()])
    tags = StringField('Tags', validators=[Optional(), Length(max=255)])
    content = TextAreaField('Content', validators=[DataRequired()])
    submit = SubmitField('Submit')

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
    submit = SubmitField('Submit')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate the session choices dynamically from the app config
        self.session.choices = [
            (key, value) for key, value in current_app.config.get('DAILY_SESSIONS', {}).items()
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
            existing_bookings = db.session.scalar(
                sa.select(sa.func.sum(Booking.rink_count))
                .where(Booking.booking_date == self.booking_date.data)
                .where(Booking.session == self.session.data)
            ) or 0
            
            total_rinks = int(current_app.config.get('RINKS', 6))
            available_rinks = total_rinks - existing_bookings
            
            if field.data > available_rinks:
                raise ValidationError(
                    f'Only {available_rinks} rinks available for this date/session. '
                    f'You requested {field.data} rinks.'
                )


class EventForm(FlaskForm):
    event_id = HiddenField('Event ID')
    name = StringField('Event Name', validators=[DataRequired(), Length(max=256)])
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