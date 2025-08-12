"""
Factory classes for creating test data using Factory Boy.
"""
import factory
from factory.alchemy import SQLAlchemyModelFactory
from datetime import date, timedelta
from app import db
from app.models import Member, Role, Booking, Team, Pool


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
    # status defaults to 'Pending' from model - don't override
    is_admin = False
    share_email = True
    share_phone = True
    joined_date = factory.Faker('date_this_decade')
    
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


class FullMemberFactory(MemberFactory):
    """Factory for creating full Member instances."""
    
    status = 'Full'


class PendingMemberFactory(MemberFactory):
    """Factory for creating pending Member instances."""
    
    status = 'Pending'


# EventFactory removed - Event model no longer exists in booking-centric architecture

class PoolFactory(SQLAlchemyModelFactory):
    """Factory for creating Pool instances."""
    
    class Meta:
        model = Pool
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = 'commit'
    
    booking_id = factory.LazyAttribute(lambda obj: BookingFactory().id)
    is_open = True
    max_players = 8


class TeamFactory(SQLAlchemyModelFactory):
    """Factory for creating Team instances."""
    
    class Meta:
        model = Team
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = 'commit'
    
    name = factory.Sequence(lambda n: f'Test Team {n}')
    booking = factory.SubFactory('tests.fixtures.factories.BookingFactory')  # Full path to avoid circular imports


class BookingFactory(SQLAlchemyModelFactory):
    """Factory for creating Booking instances."""
    
    class Meta:
        model = Booking
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = 'commit'
    
    name = factory.Sequence(lambda n: f'Test Booking {n}')
    booking_date = factory.LazyFunction(lambda: date.today() + timedelta(days=5))
    session = 1
    rink_count = 2
    organizer = factory.SubFactory(MemberFactory)
    booking_type = 'event'
    home_away = 'home'
    priority = 'Medium'
    event_type = 1  # Integer for event type
    gender = 4  # Default to "Open" 
    format = 5  # Default to "Fours - 2 Wood"


class RollUpBookingFactory(BookingFactory):
    """Factory for creating roll-up Booking instances."""
    
    booking_type = 'rollup'
    rink_count = 1
    organizer_notes = factory.Faker('text', max_nb_chars=100)


class EventBookingFactory(BookingFactory):
    """Factory for creating event Booking instances."""
    
    booking_type = 'event'
    vs = factory.Faker('company')
    name = factory.Sequence(lambda n: f'Test Event {n}')
    event_type = 1  # Social
    format = 2  # Pairs
    gender = 3  # Mixed


