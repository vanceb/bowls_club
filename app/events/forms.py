"""
Forms for event management functionality.
"""

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, BooleanField, SelectMultipleField
from wtforms.validators import DataRequired, Length, Optional
from wtforms.widgets import TextArea
import sqlalchemy as sa

from app import db
from app.models import Member


class EventForm(FlaskForm):
    """Form for creating and editing events"""
    name = StringField('Event Name', validators=[
        DataRequired(message='Event name is required'),
        Length(min=1, max=256, message='Event name must be between 1 and 256 characters')
    ])
    
    event_type = SelectField('Event Type', coerce=int, validators=[DataRequired()])
    
    gender = SelectField('Gender', coerce=int, validators=[DataRequired()])
    
    format = SelectField('Format', coerce=int, validators=[DataRequired()])
    
    scoring = StringField('Scoring System', validators=[
        Optional(),
        Length(max=64, message='Scoring system must be 64 characters or less')
    ])
    
    has_pool = BooleanField('Enable Pool Registration')
    
    def __init__(self, *args, **kwargs):
        super(EventForm, self).__init__(*args, **kwargs)
        
        from flask import current_app
        
        # Populate choices from config
        event_types = current_app.config.get('EVENT_TYPES', {})
        self.event_type.choices = [(v, k) for k, v in event_types.items()]
        
        event_genders = current_app.config.get('EVENT_GENDERS', {})
        self.gender.choices = [(v, k) for k, v in event_genders.items()]
        
        event_formats = current_app.config.get('EVENT_FORMATS', {})
        self.format.choices = [(v, k) for k, v in event_formats.items()]


class EventSelectionForm(FlaskForm):
    """Form for selecting an event"""
    event_id = SelectField('Select Event', coerce=int, validators=[DataRequired()])
    
    def __init__(self, *args, **kwargs):
        super(EventSelectionForm, self).__init__(*args, **kwargs)
        
        # Populate with available events
        from app.models import Event
        events = db.session.scalars(
            sa.select(Event).order_by(Event.name)
        ).all()
        
        self.event_id.choices = [(0, 'Select an event')] + [
            (event.id, f"{event.name} ({event.get_event_type_name()})")
            for event in events
        ]


class EventManagerAssignmentForm(FlaskForm):
    """Form for assigning event managers to events"""
    event_managers = SelectMultipleField('Event Managers', coerce=int, validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super(EventManagerAssignmentForm, self).__init__(*args, **kwargs)
        
        # Populate with ALL active members - any member can be assigned as event manager
        event_managers = db.session.scalars(
            sa.select(Member)
            .where(Member.status == 'Full')  # Only active/full members
            .order_by(Member.firstname, Member.lastname)
        ).all()
        
        self.event_managers.choices = [
            (member.id, f"{member.firstname} {member.lastname}")
            for member in event_managers
        ]