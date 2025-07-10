# Standard library imports
from datetime import datetime, timezone, date
from typing import Optional

# Third-party imports
import sqlalchemy as sa
import sqlalchemy.orm as so
from flask_login import UserMixin
from sqlalchemy import Table, Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash

# Local application imports
from app import db, login

# Association table for many-to-many relationship
member_roles = Table(
    'member_roles',
    db.Model.metadata,
    Column('member_id', Integer, ForeignKey('member.id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True)
)

# Association table for many-to-many relationship between events and members (event managers)
event_member_managers = Table(
    'event_member_managers',
    db.Model.metadata,
    Column('event_id', Integer, ForeignKey('events.id', ondelete='CASCADE'), primary_key=True),
    Column('member_id', Integer, ForeignKey('member.id', ondelete='CASCADE'), primary_key=True)
)

class Role(db.Model):
    __tablename__ = 'roles'

    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(50), nullable=False, unique=True)

    # Relationships
    members: so.Mapped[list['Member']] = so.relationship(
        'Member', secondary=member_roles, back_populates='roles'
    )

    def __repr__(self):
        return f"<Role {self.name}>"

class Member(UserMixin, db.Model):
    __tablename__ = 'member'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True,
                                                unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True,
                                             unique=True)
    phone: so.Mapped[str] = so.mapped_column(sa.String(15), index=True)
    firstname: so.Mapped[str] = so.mapped_column(sa.String(64), index=True)
    lastname: so.Mapped[str] = so.mapped_column(sa.String(64), index=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    is_admin: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False)
    gender: so.Mapped[str] = so.mapped_column(sa.String(10), default="Male")  # New field
    status: so.Mapped[str] = so.mapped_column(
        sa.String(16), default="Pending", nullable=False
    )  # New field
    share_email: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True, nullable=False)  # Privacy setting
    share_phone: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True, nullable=False)  # Privacy setting
    roles = relationship('Role', secondary=member_roles, back_populates='members')
    
    # Many-to-many relationship with events (as event manager)
    managed_events: so.Mapped[list['Event']] = so.relationship('Event', secondary=event_member_managers, back_populates='event_managers')

    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login.user_loader
def load_user(id):
    return db.session.get(Member, int(id))

class Post(db.Model):
    __tablename__ = 'posts'
    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    title: so.Mapped[str] = so.mapped_column(sa.String(255), nullable=False)
    summary: so.Mapped[str] = so.mapped_column(sa.String(255), nullable=False)
    publish_on: so.Mapped[date] = so.mapped_column(sa.Date, nullable=False)
    expires_on: so.Mapped[date] = so.mapped_column(sa.Date, nullable=False)
    pin_until: so.Mapped[Optional[date]] = so.mapped_column(sa.Date, nullable=True)
    tags: so.Mapped[Optional[str]] = so.mapped_column(sa.String(255), nullable=True)
    author_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('member.id'), nullable=False)
    markdown_filename: so.Mapped[str] = so.mapped_column(sa.String(255), nullable=False)
    html_filename: so.Mapped[str] = so.mapped_column(sa.String(255), nullable=False)
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime, default=datetime.utcnow, nullable=False)

    author: so.Mapped['Member'] = so.relationship('Member', back_populates='posts')

# Add the back_populates relationship to the Member class
Member.posts = so.relationship('Post', back_populates='author')
Member.policy_pages = so.relationship('PolicyPage', back_populates='author')

# EventManager model removed - now using Member-based system with event_member_managers association table


class Event(db.Model):
    __tablename__ = 'events'

    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(256), nullable=False)
    event_type: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False)
    gender: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False, default=4)  # Default to "Open"
    format: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False, default=5)  # Default to "Fours - 2 Wood"
    scoring: so.Mapped[Optional[str]] = so.mapped_column(sa.String(64), nullable=True)
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime, default=datetime.utcnow, nullable=False)

    # One-to-many relationship with bookings
    bookings: so.Mapped[list['Booking']] = so.relationship('Booking', back_populates='event')
    
    # Many-to-many relationship with event managers (Members with Event Manager role)
    event_managers: so.Mapped[list['Member']] = so.relationship('Member', secondary=event_member_managers, back_populates='managed_events')

    def __repr__(self):
        return f"<Event id={self.id}, name='{self.name}', type={self.event_type}, gender={self.gender}>"

    def get_event_type_name(self):
        """
        Get the human-readable name for the event type.
        """
        from flask import current_app
        event_types = current_app.config.get('EVENT_TYPES', {})
        for name, value in event_types.items():
            if value == self.event_type:
                return name
        return "Unknown"

    def get_gender_name(self):
        """
        Get the human-readable name for the event gender.
        """
        from flask import current_app
        event_genders = current_app.config.get('EVENT_GENDERS', {})
        for name, value in event_genders.items():
            if value == self.gender:
                return name
        return "Unknown"

    def get_format_name(self):
        """
        Get the human-readable name for the event format.
        """
        from flask import current_app
        event_formats = current_app.config.get('EVENT_FORMATS', {})
        for name, value in event_formats.items():
            if value == self.format:
                return name
        return "Unknown"


class Booking(db.Model):
    __tablename__ = 'bookings'

    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    booking_date: so.Mapped[date] = so.mapped_column(sa.Date, nullable=False)
    session: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False)
    rink_count: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False, default=1)
    priority: so.Mapped[Optional[str]] = so.mapped_column(sa.String(50), nullable=True)
    event_id: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer, sa.ForeignKey('events.id'), nullable=True)

    # Many-to-one relationship with event
    event: so.Mapped[Optional['Event']] = so.relationship('Event', back_populates='bookings')

    def __repr__(self):
        return f"<Booking id={self.id}, date={self.booking_date}, session={self.session}, rink_count={self.rink_count}, event_id={self.event_id}>"


class PolicyPage(db.Model):
    __tablename__ = 'policy_pages'
    
    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    title: so.Mapped[str] = so.mapped_column(sa.String(255), nullable=False)
    slug: so.Mapped[str] = so.mapped_column(sa.String(255), nullable=False, unique=True)
    description: so.Mapped[str] = so.mapped_column(sa.String(255), nullable=False)
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, nullable=False, default=True)
    show_in_footer: so.Mapped[bool] = so.mapped_column(sa.Boolean, nullable=False, default=True)
    sort_order: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False, default=0)
    author_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('member.id'), nullable=False)
    markdown_filename: so.Mapped[str] = so.mapped_column(sa.String(255), nullable=False)
    html_filename: so.Mapped[str] = so.mapped_column(sa.String(255), nullable=False)
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime, default=datetime.utcnow, nullable=False)
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    author: so.Mapped['Member'] = so.relationship('Member', back_populates='policy_pages')

    def __repr__(self):
        return f"<PolicyPage id={self.id}, title='{self.title}', slug='{self.slug}', active={self.is_active}>"

