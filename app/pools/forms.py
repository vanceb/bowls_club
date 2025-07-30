"""
Pool management forms.
"""

from datetime import datetime, date
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, BooleanField, DateTimeField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Optional, NumberRange, ValidationError
from wtforms.widgets import NumberInput, TextArea
import sqlalchemy as sa

from app import db
from app.models import Member, Pool


class PoolForm(FlaskForm):
    """
    Form for creating and managing pools.
    """
    is_open = BooleanField('Pool is Open', default=True)
    max_players = IntegerField('Maximum Players', 
                              validators=[Optional(), NumberRange(min=1, max=100)],
                              widget=NumberInput(),
                              render_kw={'placeholder': 'Leave empty for no limit'})
    auto_close_date = DateTimeField('Auto Close Date',
                                   validators=[Optional()],
                                   format='%Y-%m-%d %H:%M')
    
    def validate_auto_close_date(self, field):
        """Validate that auto close date is in the future"""
        if field.data and field.data <= datetime.now():
            raise ValidationError('Auto close date must be in the future.')


class PoolRegistrationForm(FlaskForm):
    """
    Form for registering members to a pool.
    """
    member_id = SelectField('Member', 
                           validators=[DataRequired()],
                           coerce=int)
    
    def validate_member_id(self, field):
        """Validate that the member exists and is active"""
        member = db.session.get(Member, field.data)
        if not member:
            raise ValidationError('Invalid member selected.')
        if member.status != 'Active':
            raise ValidationError('Only active members can be registered.')


class PoolSearchForm(FlaskForm):
    """
    Form for searching and filtering pools.
    """
    pool_type = SelectField('Pool Type',
                           choices=[('', 'All Pools'),
                                   ('event', 'Event Pools'),
                                   ('booking', 'Booking Pools')],
                           default='')
    status = SelectField('Status',
                        choices=[('', 'All Statuses'),
                                ('open', 'Open'),
                                ('closed', 'Closed')],
                        default='')
    search_term = StringField('Search',
                             render_kw={'placeholder': 'Search pools...'})


class BulkRegistrationForm(FlaskForm):
    """
    Form for bulk member registration to pools.
    """
    member_ids = TextAreaField('Member IDs',
                              validators=[DataRequired()],
                              widget=TextArea(),
                              render_kw={
                                  'placeholder': 'Enter member IDs separated by commas or newlines',
                                  'rows': 5
                              })
    
    def validate_member_ids(self, field):
        """Validate that all member IDs are valid"""
        try:
            # Parse member IDs from the text
            member_ids_text = field.data.strip()
            if not member_ids_text:
                raise ValidationError('Please enter at least one member ID.')
            
            # Split by commas and newlines, clean up
            raw_ids = []
            for line in member_ids_text.split('\n'):
                for id_str in line.split(','):
                    id_str = id_str.strip()
                    if id_str:
                        raw_ids.append(id_str)
            
            # Convert to integers
            member_ids = []
            for id_str in raw_ids:
                try:
                    member_ids.append(int(id_str))
                except ValueError:
                    raise ValidationError(f'Invalid member ID: {id_str}')
            
            if not member_ids:
                raise ValidationError('Please enter at least one valid member ID.')
            
            # Validate that all members exist and are active
            members = db.session.scalars(
                sa.select(Member).where(Member.id.in_(member_ids))
            ).all()
            
            found_ids = {member.id for member in members}
            missing_ids = set(member_ids) - found_ids
            if missing_ids:
                raise ValidationError(f'Member IDs not found: {", ".join(map(str, missing_ids))}')
            
            inactive_members = [member for member in members if member.status != 'Active']
            if inactive_members:
                inactive_names = [f"{m.firstname} {m.lastname}" for m in inactive_members]
                raise ValidationError(f'Inactive members cannot be registered: {", ".join(inactive_names)}')
            
            # Store parsed member IDs for use in the route
            self._parsed_member_ids = member_ids
            
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f'Error parsing member IDs: {str(e)}')
    
    def get_parsed_member_ids(self):
        """Get the parsed and validated member IDs"""
        return getattr(self, '_parsed_member_ids', [])


class PoolSettingsForm(FlaskForm):
    """
    Form for advanced pool settings.
    """
    is_open = BooleanField('Pool is Open')
    max_players = IntegerField('Maximum Players',
                              validators=[Optional(), NumberRange(min=1, max=200)],
                              widget=NumberInput())
    auto_close_date = DateTimeField('Auto Close Date',
                                   validators=[Optional()],
                                   format='%Y-%m-%d %H:%M')
    registration_message = TextAreaField('Registration Message',
                                        validators=[Optional()],
                                        widget=TextArea(),
                                        render_kw={
                                            'placeholder': 'Optional message shown to members when registering',
                                            'rows': 3
                                        })
    
    def validate_auto_close_date(self, field):
        """Validate that auto close date is reasonable"""
        if field.data:
            if field.data <= datetime.now():
                raise ValidationError('Auto close date must be in the future.')
            # Don't allow dates more than 1 year in the future
            if field.data > datetime.now().replace(year=datetime.now().year + 1):
                raise ValidationError('Auto close date cannot be more than 1 year in the future.')


class PoolStatusUpdateForm(FlaskForm):
    """
    Form for updating member status in a pool.
    """
    status = SelectField('Status',
                        choices=[('registered', 'Registered'),
                                ('selected', 'Selected'),
                                ('declined', 'Declined')],
                        validators=[DataRequired()])
    notes = TextAreaField('Notes',
                         validators=[Optional()],
                         widget=TextArea(),
                         render_kw={
                             'placeholder': 'Optional notes about this status change',
                             'rows': 2
                         })