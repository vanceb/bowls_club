"""
Factory classes for creating test data using Factory Boy.
"""
import factory
from factory.alchemy import SQLAlchemyModelFactory
from app import db
from app.models import Member, Role


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