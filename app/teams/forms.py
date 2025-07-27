"""
Team management forms
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SelectMultipleField, HiddenField
from wtforms.validators import DataRequired, Length, Optional
from wtforms.widgets import TextArea
import sqlalchemy as sa

from app import db
from app.models import Member


class TeamForm(FlaskForm):
    """Form for creating/editing teams"""
    team_name = StringField('Team Name', validators=[
        DataRequired(message='Team name is required'),
        Length(min=1, max=100, message='Team name must be between 1 and 100 characters')
    ])
    
    member_ids = TextAreaField('Member IDs (comma-separated)', validators=[Optional()], 
                              render_kw={"placeholder": "Enter member IDs separated by commas (e.g., 1,2,3)"})


class TeamMemberForm(FlaskForm):
    """Form for adding members to teams"""
    member_id = SelectField('Member', coerce=int, validators=[DataRequired()])
    position = SelectField('Position', validators=[DataRequired()], choices=[
        ('Lead', 'Lead'),
        ('Second', 'Second'), 
        ('Third', 'Third'),
        ('Skip', 'Skip'),
        ('Player', 'Player')
    ])
    
    def __init__(self, *args, **kwargs):
        super(TeamMemberForm, self).__init__(*args, **kwargs)
        # Populate member choices
        self.member_id.choices = [(0, 'Select a member')] + [
            (member.id, f"{member.firstname} {member.lastname}")
            for member in db.session.scalars(
                sa.select(Member)
                .where(Member.status.in_(['Full', 'Life', 'Social']))
                .order_by(Member.firstname, Member.lastname)
            ).all()
        ]


class SubstitutionForm(FlaskForm):
    """Form for player substitutions"""
    booking_team_member_id = HiddenField('Team Member ID', validators=[DataRequired()])
    new_member_id = SelectField('Substitute Player', coerce=int, validators=[DataRequired()])
    reason = TextAreaField('Reason for Substitution', validators=[Optional()],
                          render_kw={"placeholder": "Optional reason for the substitution"})
    
    def __init__(self, *args, **kwargs):
        super(SubstitutionForm, self).__init__(*args, **kwargs)
        # Populate member choices
        self.new_member_id.choices = [(0, 'Select substitute player')] + [
            (member.id, f"{member.firstname} {member.lastname}")
            for member in db.session.scalars(
                sa.select(Member)
                .where(Member.status.in_(['Full', 'Life', 'Social']))
                .order_by(Member.firstname, Member.lastname)
            ).all()
        ]


class AvailabilityForm(FlaskForm):
    """Form for updating member availability"""
    status = SelectField('Availability Status', validators=[DataRequired()], choices=[
        ('pending', 'Pending'),
        ('available', 'Available'),
        ('unavailable', 'Unavailable')
    ])
    booking_team_member_id = HiddenField('Team Member ID', validators=[DataRequired()])