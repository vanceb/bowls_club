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
    phone: so.Mapped[Optional[str]] = so.mapped_column(sa.String(15), index=True)
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
    last_login: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime, nullable=True)  # Last successful login
    last_seen: so.Mapped[Optional[date]] = so.mapped_column(sa.Date, nullable=True)  # Last activity date (daily updates only)
    lockout: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False, nullable=False)  # User lockout status
    roles = relationship('Role', secondary=member_roles, back_populates='members')
    
    # Many-to-many relationship with events (as event manager)
    managed_events: so.Mapped[list['Event']] = so.relationship('Event', secondary=event_member_managers, back_populates='event_managers')

    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        # Note: Audit logging for password changes is handled in the calling route
        # to ensure proper user context and transaction management

    def check_password(self, password):
        if self.password_hash is None:
            return False
        return check_password_hash(self.password_hash, password)
    
    @staticmethod
    def is_bootstrap_mode():
        """Check if the system is in bootstrap mode (no users exist)."""
        return db.session.query(Member).count() == 0

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
    has_pool: so.Mapped[bool] = so.mapped_column(sa.Boolean, nullable=False, default=False)

    # One-to-many relationship with bookings
    bookings: so.Mapped[list['Booking']] = so.relationship('Booking', back_populates='event')
    
    # One-to-many relationship with event teams
    event_teams: so.Mapped[list['EventTeam']] = so.relationship('EventTeam', back_populates='event', cascade='all, delete-orphan')
    
    # One-to-one relationship with event pool
    pool: so.Mapped[Optional['EventPool']] = so.relationship('EventPool', back_populates='event', uselist=False, cascade='all, delete-orphan')
    
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

    def has_teams(self):
        """Check if the event has any teams defined"""
        return len(self.event_teams) > 0
    
    def has_complete_teams(self):
        """Check if the event has at least one team with all positions filled"""
        if not self.has_teams():
            return False
        
        from flask import current_app
        team_positions = current_app.config.get('TEAM_POSITIONS', {})
        required_positions = len(team_positions.get(self.format, []))
        
        for team in self.event_teams:
            if len(team.team_members) == required_positions:
                return True
        return False
    
    def is_ready_for_bookings(self):
        """Check if the event is ready for booking creation"""
        return self.has_teams()  # At minimum, need teams defined

    # Pool-related methods
    def has_pool_enabled(self):
        """Check if this event has pool functionality enabled"""
        return bool(self.has_pool) and self.pool is not None
    
    def is_pool_open(self):
        """Check if the event pool is open for registration"""
        return self.has_pool_enabled() and self.pool.is_open
    
    def get_pool_member_count(self):
        """Get the number of members registered in the pool"""
        if not self.has_pool_enabled():
            return 0
        return len(self.pool.registrations)
    
    def get_registration_status(self):
        """Get event registration status: 'open', 'closed', 'no_pool'"""
        if not self.has_pool_enabled():
            return 'no_pool'
        return 'open' if self.pool.is_open else 'closed'
    
    def can_create_teams_from_pool(self):
        """Check if teams can be created from pool members"""
        if not self.has_pool_enabled():
            return False, "No pool enabled for this event"
        
        registered_members = self.pool.get_registered_members()
        if not registered_members:
            return False, "No registered members in pool"
        
        from flask import current_app
        team_positions = current_app.config.get('TEAM_POSITIONS', {})
        positions = team_positions.get(self.format, [])
        
        if not positions:
            return False, f"No team positions configured for format: {self.format}"
        
        team_size = len(positions)
        if len(registered_members) < team_size:
            return False, f"Not enough registered members ({len(registered_members)}) for a complete team (need {team_size})"
        
        return True, f"Can create {len(registered_members) // team_size} teams"
    
    def can_create_booking_from_teams(self):
        """Check if a booking can be created from existing teams"""
        if not self.event_teams:
            return False, "No teams exist for this event"
        
        teams_with_members = [team for team in self.event_teams if team.team_members]
        if not teams_with_members:
            return False, "No teams have assigned members"
        
        return True, f"Can create booking with {len(teams_with_members)} teams"
    
    def get_workflow_status(self):
        """Get the current status of the pool-to-team-to-booking workflow"""
        status = {
            'pool_enabled': self.has_pool_enabled(),
            'pool_open': self.is_pool_open(),
            'pool_members': self.get_pool_member_count(),
            'registered_members': len(self.pool.get_registered_members()) if self.has_pool_enabled() else 0,
            'teams_count': len(self.event_teams),
            'teams_with_members': len([t for t in self.event_teams if t.team_members]),
            'bookings_count': len(self.bookings)
        }
        
        # Determine workflow stage
        if not status['pool_enabled']:
            status['stage'] = 'no_pool'
        elif status['pool_members'] == 0:
            status['stage'] = 'awaiting_registrations'
        elif status['registered_members'] == 0 and status['teams_count'] == 0:
            status['stage'] = 'ready_for_selection'
        elif status['teams_count'] == 0:
            status['stage'] = 'ready_for_teams'
        elif status['bookings_count'] == 0:
            status['stage'] = 'ready_for_booking'
        else:
            status['stage'] = 'complete'
        
        return status


class EventPool(db.Model):
    """
    Event Pool model - manages member registration for events
    Based on existing event_pools table structure
    """
    __tablename__ = 'event_pools'

    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    event_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('events.id'), nullable=False)
    is_open: so.Mapped[bool] = so.mapped_column(sa.Boolean, nullable=False, default=True)
    auto_close_date: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime, nullable=True)
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime, default=datetime.utcnow, nullable=False)
    closed_at: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime, nullable=True)

    # Relationships
    event: so.Mapped['Event'] = so.relationship('Event', back_populates='pool')
    registrations: so.Mapped[list['PoolRegistration']] = so.relationship('PoolRegistration', back_populates='pool', cascade='all, delete-orphan')

    def __repr__(self):
        status = "Open" if self.is_open else "Closed"
        return f"<EventPool id={self.id}, event='{self.event.name if self.event else 'Unknown'}', status={status}>"

    def close_pool(self):
        """Close the pool for new registrations"""
        if self.is_open:
            self.is_open = False
            self.closed_at = datetime.utcnow()

    def reopen_pool(self):
        """Reopen the pool for new registrations"""
        if not self.is_open:
            self.is_open = True
            self.closed_at = None

    def get_registered_members(self):
        """Get all members currently registered in the pool"""
        return [reg.member for reg in self.registrations]

    def is_member_registered(self, member_id):
        """Check if a member is registered in this pool"""
        return any(reg.member_id == member_id for reg in self.registrations)

    def get_member_registration(self, member_id):
        """Get the registration record for a specific member"""
        return next((reg for reg in self.registrations if reg.member_id == member_id), None)

    def get_registration_count(self):
        """Get the total number of active registrations"""
        return len(self.registrations)


class PoolRegistration(db.Model):
    """
    Pool Registration model - tracks individual member registrations in event pools
    Based on existing pool_members table structure
    """
    __tablename__ = 'pool_members'

    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    pool_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('event_pools.id'), nullable=False)
    member_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('member.id'), nullable=False)
    registered_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime, default=datetime.utcnow, nullable=False)
    last_updated: so.Mapped[datetime] = so.mapped_column(sa.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    pool: so.Mapped['EventPool'] = so.relationship('EventPool', back_populates='registrations')
    member: so.Mapped['Member'] = so.relationship('Member')

    def __repr__(self):
        return f"<PoolRegistration id={self.id}, member='{self.member.firstname} {self.member.lastname}' if self.member else 'Unknown'>"

    @property
    def is_active(self):
        """Check if registration is active - if record exists, it's active"""
        return True


class Booking(db.Model):
    __tablename__ = 'bookings'

    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    booking_date: so.Mapped[date] = so.mapped_column(sa.Date, nullable=False)
    session: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False)
    rink_count: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False, default=1)
    priority: so.Mapped[Optional[str]] = so.mapped_column(sa.String(50), nullable=True)
    vs: so.Mapped[Optional[str]] = so.mapped_column(sa.String(128), nullable=True)  # Opposition team name
    home_away: so.Mapped[Optional[str]] = so.mapped_column(sa.String(10), nullable=True)  # 'home', 'away', or 'neutral'
    event_id: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer, sa.ForeignKey('events.id'), nullable=True)
    
    # Roll-up booking fields
    booking_type: so.Mapped[str] = so.mapped_column(sa.String(20), default='event', nullable=False)  # 'event' or 'rollup'
    organizer_id: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer, sa.ForeignKey('member.id'), nullable=True)
    organizer_notes: so.Mapped[Optional[str]] = so.mapped_column(sa.Text, nullable=True)

    # Many-to-one relationship with event
    event: so.Mapped[Optional['Event']] = so.relationship('Event', back_populates='bookings')
    
    # Many-to-one relationship with organizer (for roll-ups)
    organizer: so.Mapped[Optional['Member']] = so.relationship('Member', back_populates='organized_rollups', foreign_keys=[organizer_id])
    
    # One-to-many relationship with booking teams (for events)
    booking_teams: so.Mapped[list['BookingTeam']] = so.relationship('BookingTeam', back_populates='booking', cascade='all, delete-orphan')
    
    # One-to-many relationship with booking players (for roll-ups)
    booking_players: so.Mapped[list['BookingPlayer']] = so.relationship('BookingPlayer', back_populates='booking', cascade='all, delete-orphan')

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


class EventTeam(db.Model):
    __tablename__ = 'event_teams'

    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    event_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('events.id'), nullable=False)
    team_name: so.Mapped[str] = so.mapped_column(sa.String(100), nullable=False)
    team_number: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False)  # 1, 2, 3, etc.
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime, default=datetime.utcnow, nullable=False)

    # Many-to-one relationship with event
    event: so.Mapped['Event'] = so.relationship('Event', back_populates='event_teams')
    
    # One-to-many relationship with team members
    team_members: so.Mapped[list['TeamMember']] = so.relationship('TeamMember', back_populates='event_team', cascade='all, delete-orphan')
    
    # One-to-many relationship with booking teams (when copied)
    booking_teams: so.Mapped[list['BookingTeam']] = so.relationship('BookingTeam', back_populates='event_team')

    def __repr__(self):
        return f"<EventTeam id={self.id}, name='{self.team_name}', event_id={self.event_id}>"

    def get_team_size(self):
        """Get the expected team size based on the event format"""
        from flask import current_app
        team_positions = current_app.config.get('TEAM_POSITIONS', {})
        return len(team_positions.get(self.event.format, []))

    def get_available_positions(self):
        """Get the list of positions for this team based on event format"""
        from flask import current_app
        team_positions = current_app.config.get('TEAM_POSITIONS', {})
        return team_positions.get(self.event.format, [])


class BookingTeam(db.Model):
    __tablename__ = 'booking_teams'

    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    booking_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('bookings.id'), nullable=False)
    event_team_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('event_teams.id'), nullable=False)
    team_name: so.Mapped[str] = so.mapped_column(sa.String(100), nullable=False)
    team_number: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False)
    substitution_log: so.Mapped[Optional[str]] = so.mapped_column(sa.Text, nullable=True)  # JSON log of substitutions
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime, default=datetime.utcnow, nullable=False)

    # Many-to-one relationships
    booking: so.Mapped['Booking'] = so.relationship('Booking', back_populates='booking_teams')
    event_team: so.Mapped['EventTeam'] = so.relationship('EventTeam', back_populates='booking_teams')
    
    # One-to-many relationship with booking team members
    booking_team_members: so.Mapped[list['BookingTeamMember']] = so.relationship('BookingTeamMember', back_populates='booking_team', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<BookingTeam id={self.id}, name='{self.team_name}', booking_id={self.booking_id}>"

    def get_team_size(self):
        """Get the expected team size based on the event format"""
        return self.event_team.get_team_size()

    def get_available_positions(self):
        """Get the list of positions for this team based on event format"""
        return self.event_team.get_available_positions()


class TeamMember(db.Model):
    __tablename__ = 'team_members'

    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    event_team_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('event_teams.id'), nullable=False)
    member_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('member.id'), nullable=False)
    position: so.Mapped[str] = so.mapped_column(sa.String(20), nullable=False)  # Lead, Second, Third, Skip, Player
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime, default=datetime.utcnow, nullable=False)

    # Many-to-one relationships
    event_team: so.Mapped['EventTeam'] = so.relationship('EventTeam', back_populates='team_members')
    member: so.Mapped['Member'] = so.relationship('Member', back_populates='team_memberships')

    def __repr__(self):
        return f"<TeamMember id={self.id}, member_id={self.member_id}, position='{self.position}'>"


class BookingTeamMember(db.Model):
    __tablename__ = 'booking_team_members'

    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    booking_team_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('booking_teams.id'), nullable=False)
    member_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('member.id'), nullable=False)
    position: so.Mapped[str] = so.mapped_column(sa.String(20), nullable=False)  # Lead, Second, Third, Skip, Player
    is_substitute: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False, nullable=False)
    availability_status: so.Mapped[str] = so.mapped_column(sa.String(20), default='pending', nullable=False)  # 'pending', 'available', 'unavailable'
    confirmed_at: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime, nullable=True)
    substituted_at: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime, nullable=True)
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime, default=datetime.utcnow, nullable=False)

    # Many-to-one relationships
    booking_team: so.Mapped['BookingTeam'] = so.relationship('BookingTeam', back_populates='booking_team_members')
    member: so.Mapped['Member'] = so.relationship('Member', back_populates='booking_team_memberships')

    def __repr__(self):
        return f"<BookingTeamMember id={self.id}, member_id={self.member_id}, position='{self.position}', status='{self.availability_status}'>"


class BookingPlayer(db.Model):
    __tablename__ = 'booking_players'

    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    booking_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('bookings.id'), nullable=False)
    member_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('member.id'), nullable=False)
    status: so.Mapped[str] = so.mapped_column(sa.String(20), default='pending', nullable=False)  # 'confirmed', 'pending', 'declined'
    invited_by: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('member.id'), nullable=False)
    response_at: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime, nullable=True)
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime, default=datetime.utcnow, nullable=False)

    # Many-to-one relationships
    booking: so.Mapped['Booking'] = so.relationship('Booking', back_populates='booking_players')
    member: so.Mapped['Member'] = so.relationship('Member', foreign_keys=[member_id], back_populates='rollup_invitations')
    inviter: so.Mapped['Member'] = so.relationship('Member', foreign_keys=[invited_by], back_populates='sent_rollup_invitations')

    def __repr__(self):
        return f"<BookingPlayer id={self.id}, booking_id={self.booking_id}, member_id={self.member_id}, status='{self.status}'>"


# Add team-related relationships to Member model
Member.team_memberships = so.relationship('TeamMember', back_populates='member')
Member.booking_team_memberships = so.relationship('BookingTeamMember', back_populates='member')

# Add roll-up related relationships to Member model
Member.organized_rollups = so.relationship('Booking', back_populates='organizer', foreign_keys='Booking.organizer_id')
Member.rollup_invitations = so.relationship('BookingPlayer', foreign_keys='BookingPlayer.member_id', back_populates='member')
Member.sent_rollup_invitations = so.relationship('BookingPlayer', foreign_keys='BookingPlayer.invited_by', back_populates='inviter')

