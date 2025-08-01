"""
Factory classes for creating test data using Factory Boy.
"""
import factory
from factory.alchemy import SQLAlchemyModelFactory
from datetime import date, timedelta
from app import db
from app.models import Member, Role, Booking, Event, BookingPlayer, BookingTeam, BookingTeamMember


class RoleFactory(SQLAlchemyModelFactory):
    """Factory for creating Role instances."""
    
    class Meta:
        model = Role
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = 'commit'
    
    name = factory.Sequence(lambda n: f'Test Role {n}')


class MemberFactory(SQLAlchemyModelFactory):
    """Factory for creating Member instances."""
    
    class Meta:
        model = Member
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = 'commit'
    
    username = factory.Sequence(lambda n: f'testuser{n}')
    firstname = factory.Faker('first_name')
    lastname = factory.Faker('last_name')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    phone = factory.Faker('phone_number')
    status = 'Full'
    is_admin = False
    share_email = True
    share_phone = True
    
    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        """Set password for the member."""
        if not create:
            return
        if extracted:
            obj.set_password(extracted)
        else:
            obj.set_password('defaultpassword123')


class AdminMemberFactory(MemberFactory):
    """Factory for creating admin Member instances."""
    
    is_admin = True
    status = 'Full'
    
    @factory.post_generation
    def roles(obj, create, extracted, **kwargs):
        """Assign roles to admin member."""
        if not create:
            return
        if extracted:
            obj.roles = extracted


class PendingMemberFactory(MemberFactory):
    """Factory for creating pending Member instances."""
    
    status = 'Pending'


class EventFactory(SQLAlchemyModelFactory):
    """Factory for creating Event instances."""
    
    class Meta:
        model = Event
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = 'commit'
    
    name = factory.Sequence(lambda n: f'Test Event {n}')
    event_type = 1  # Social
    format = 2  # Pairs
    gender = 3  # Mixed


# EventTeamFactory removed - teams are now created from pools via bookings


class BookingFactory(SQLAlchemyModelFactory):
    """Factory for creating Booking instances."""
    
    class Meta:
        model = Booking
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = 'commit'
    
    booking_date = factory.LazyFunction(lambda: date.today() + timedelta(days=5))
    session = 1
    rink_count = 2
    organizer = factory.SubFactory(MemberFactory)
    booking_type = 'event'
    home_away = 'home'
    priority = 'Medium'


class RollUpBookingFactory(BookingFactory):
    """Factory for creating roll-up Booking instances."""
    
    booking_type = 'rollup'
    rink_count = 1
    organizer_notes = factory.Faker('text', max_nb_chars=100)


class EventBookingFactory(BookingFactory):
    """Factory for creating event Booking instances."""
    
    event = factory.SubFactory(EventFactory)
    vs = factory.Faker('company')


class BookingPlayerFactory(SQLAlchemyModelFactory):
    """Factory for creating BookingPlayer instances."""
    
    class Meta:
        model = BookingPlayer
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = 'commit'
    
    booking = factory.SubFactory(RollUpBookingFactory)
    member = factory.SubFactory(MemberFactory)
    status = 'pending'
    invited_by = factory.SelfAttribute('booking.organizer.id')


class BookingTeamFactory(SQLAlchemyModelFactory):
    """Factory for creating BookingTeam instances."""
    
    class Meta:
        model = BookingTeam
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = 'commit'
    
    booking = factory.SubFactory(EventBookingFactory)
    # event_team removed - teams are now created directly from pools
    team_name = factory.Sequence(lambda n: f'Team {n}')
    team_number = factory.Sequence(lambda n: n)


class BookingTeamMemberFactory(SQLAlchemyModelFactory):
    """Factory for creating BookingTeamMember instances."""
    
    class Meta:
        model = BookingTeamMember
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = 'commit'
    
    team = factory.SubFactory(BookingTeamFactory)
    member = factory.SubFactory(MemberFactory)
    position = 'Lead'