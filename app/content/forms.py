# Standard library imports
from datetime import date, timedelta

# Third-party imports
from flask import current_app
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileSize
from wtforms import (
    StringField, BooleanField, SubmitField, TextAreaField, DateField, IntegerField, MultipleFileField, SelectField, RadioField
)
from wtforms.validators import (
    DataRequired, Length, Optional, NumberRange, ValidationError
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
    
    # Image upload field for multiple images
    images = MultipleFileField(
        'Upload Images',
        validators=[
            Optional()
            # FileAllowed validation will be done manually in the route
        ]
    )
    
    # Hero image selection field - will be populated dynamically with uploaded images
    hero_image = RadioField(
        'Hero Image',
        choices=[('', 'No hero image')],
        validators=[Optional()],
        default=''
    )
    
    def validate_images(self, field):
        """Custom validation for image uploads using config values"""
        if not field.data:
            return
        
        allowed_types = current_app.config.get('IMAGE_ALLOWED_TYPES', ['jpg', 'jpeg', 'png'])
        for file in field.data:
            if file and file.filename:
                if '.' not in file.filename:
                    raise ValidationError('Invalid file format.')
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext not in allowed_types:
                    allowed_str = ', '.join(allowed_types)
                    raise ValidationError(f'Only {allowed_str} files are allowed!')
    
    def validate_hero_image(self, field):
        """Custom validation for hero image selection"""
        if not field.data:
            return  # Hero image is optional
        
        # We can't validate hero image during form validation because:
        # 1. For new posts, the images haven't been saved yet
        # 2. For existing posts, we need the post ID to check the directory
        # Hero image validation will be done in the route handler instead
        pass
    
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