# Standard library imports
from datetime import date, timedelta

# Third-party imports
from flask import current_app
from flask_wtf import FlaskForm
from wtforms import (
    StringField, BooleanField, SubmitField, TextAreaField, DateField, IntegerField
)
from wtforms.validators import (
    DataRequired, Length, Optional, NumberRange
)

class WritePostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=1, max=255)])
    summary = TextAreaField('Summary', validators=[DataRequired(), Length(min=1, max=255)])
    publish_on = DateField('Publish On', default=date.today, validators=[DataRequired()])
    expires_on = DateField(
        'Expires On',
        default=lambda: date.today() + timedelta(days=current_app.config.get('POST_EXPIRATION_DAYS', 30)),
        validators=[DataRequired()]
    )
    pin_until = DateField('Pin Until', validators=[Optional()])
    tags = StringField('Tags', validators=[Optional(), Length(max=255)])
    content = TextAreaField('Content', validators=[DataRequired(), Length(min=1, max=10000)])
    submit = SubmitField('Submit')


class PolicyPageForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=1, max=255)])
    slug = StringField('URL Slug', validators=[DataRequired(), Length(min=1, max=255)])
    description = TextAreaField('Description', validators=[DataRequired(), Length(min=1, max=255)])
    is_active = BooleanField('Active', default=True)
    show_in_footer = BooleanField('Show in Footer', default=True)
    sort_order = IntegerField('Sort Order', validators=[Optional(), NumberRange(min=0, max=9999)], default=0)
    content = TextAreaField('Content', validators=[DataRequired(), Length(min=1, max=10000)])
    submit = SubmitField('Submit')