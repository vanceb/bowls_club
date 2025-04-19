from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, HiddenField, SelectMultipleField, TextAreaField, DateField
from wtforms.widgets import CheckboxInput, ListWidget
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, Length, Optional
import sqlalchemy as sa
from app import db
from app.models import Member
from datetime import date, timedelta
from flask import current_app

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
    pin = BooleanField('Pin')
    pin_until = DateField('Pin Until', validators=[Optional()])
    tags = StringField('Tags', validators=[Optional(), Length(max=255)])
    content = TextAreaField('Content', validators=[DataRequired()])
    submit = SubmitField('Submit')