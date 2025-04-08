from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, Length, Optional
import sqlalchemy as sa
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
    password = PasswordField('Password', validators=[DataRequired(message="A password is required"), Length(min=8, message="Password must be at least 8 charachters long"), EqualTo('password2', "Passwords must match.")])
    password2 = PasswordField('Repeat Password', validators=[DataRequired()])
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