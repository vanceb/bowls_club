"""
Test configuration and fixtures for the Bowls Club application.
"""
import pytest
import tempfile
import os
from app import create_app, db
from app.models import Member, Role, Booking, Pool, PoolRegistration, Team, TeamMember
from tests.fixtures.factories import BookingFactory, MemberFactory, AdminMemberFactory, FullMemberFactory, PendingMemberFactory

# Set environment variables for testing
os.environ['SECRET_KEY'] = 'test-secret-key-for-testing-only'
os.environ['MAIL_SUPPRESS_SEND'] = 'true'


@pytest.fixture(scope='session')
def app():
    """Create application for testing."""
    app = create_app('testing')
    
    # Create application context and set up database
    with app.app_context():
        # Import all models to ensure they are loaded
        from app.models import Member, Role, Booking, Pool, PoolRegistration, Team, TeamMember
        
        # Ensure all models are registered with SQLAlchemy
        # This forces SQLAlchemy to process all model definitions
        from app import models
        
        # Create all database tables
        db.create_all()
        
        # Debug: Check if tables were created
        import sqlalchemy as sa
        inspector = sa.inspect(db.engine)
        tables = inspector.get_table_names()
        if 'member' not in tables:
            raise RuntimeError(f"Database setup failed. Tables created: {tables}")
        
        yield app
        
        # Clean up after all tests in session
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create test CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def db_session(app):
    """Create database session for testing."""
    with app.app_context():
        # Provide the session (tables are already created in app fixture)
        yield db.session
        
        # Clean up - remove any data created during the test
        # Note: We don't drop tables here since they're session-scoped
        # Just clear the data for the next test
        try:
            # Clear all tables for clean state between tests
            for table in reversed(db.metadata.sorted_tables):
                db.session.execute(table.delete())
            db.session.commit()
        except Exception:
            # If there's an error, rollback
            db.session.rollback()
        finally:
            db.session.remove()


@pytest.fixture
def core_roles(db_session):
    """Create core roles for testing."""
    roles = []
    for role_name in ['User Manager', 'Content Manager', 'Event Manager']:
        # Check if role already exists
        existing_role = db_session.query(Role).filter_by(name=role_name).first()
        if existing_role:
            roles.append(existing_role)
        else:
            role = Role(name=role_name)
            db_session.add(role)
            roles.append(role)
    
    db_session.commit()
    return roles


@pytest.fixture
def test_member(db_session):
    """Create a basic test member."""
    member = FullMemberFactory.create(
        firstname='Test',
        lastname='User',
        password='testpassword123'
    )
    return member


@pytest.fixture
def admin_member(db_session, core_roles):
    """Create an admin test member with all roles."""
    member = AdminMemberFactory.create(
        firstname='Admin',
        lastname='User',
        password='adminpassword123',
        roles=core_roles  # Assign all core roles
    )
    return member


@pytest.fixture
def pending_member(db_session):
    """Create a pending member for testing."""
    member = PendingMemberFactory.create(
        firstname='Pending',
        lastname='User',
        password='pendingpassword123'
    )
    return member


@pytest.fixture
def user_manager_member(db_session, core_roles):
    """Create a member with User Manager role."""
    user_manager_role = next(role for role in core_roles if role.name == 'User Manager')
    member = FullMemberFactory.create(
        firstname='User',
        lastname='Manager',
        password='managerpassword123'
    )
    member.roles = [user_manager_role]
    db_session.add(member)
    db_session.commit()
    return member


@pytest.fixture
def authenticated_client(client, test_member):
    """Create an authenticated client session."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(test_member.id)
        sess['_fresh'] = True
    return client


@pytest.fixture
def admin_client(client, admin_member):
    """Create an authenticated admin client session."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_member.id)
        sess['_fresh'] = True
    return client


@pytest.fixture
def test_booking(db_session):
    """Create a test booking."""
    from datetime import datetime, timedelta, date
    booking = BookingFactory.create(
        name='Test Conftest Booking',
        booking_date=date.today() + timedelta(days=1),
        session=1,
        rink_count=2,
        event_type=1,
        gender=4,
        format=5
    )
    return booking


@pytest.fixture
def test_pool(db_session, test_booking):
    """Create a test pool."""
    pool = Pool(booking_id=test_booking.id, is_open=True)
    db_session.add(pool)
    db_session.commit()
    return pool


@pytest.fixture
def test_booking_with_pool(db_session, test_booking):
    """Create a test booking with pool."""
    pool = Pool(booking_id=test_booking.id, is_open=True)
    db_session.add(pool)
    db_session.commit()
    test_booking.pool = pool
    return test_booking


@pytest.fixture
def test_event(db_session):
    """Create a test event (booking)."""
    from datetime import datetime, timedelta, date
    event = BookingFactory.create(
        name='Test Event',
        booking_date=date.today() + timedelta(days=7),
        session=1,
        rink_count=2,
        booking_type='event',
        event_type=1,  # Social
        gender=4,  # Open
        format=5   # Fours - 2 Wood
    )
    return event


@pytest.fixture
def test_event_with_pool(db_session, test_event):
    """Create a test event with pool."""
    pool = Pool(booking_id=test_event.id, is_open=True)
    db_session.add(pool)
    db_session.commit()
    test_event.pool = pool
    return test_event


@pytest.fixture
def event_manager_member(db_session, core_roles):
    """Create a member with Event Manager role."""
    event_manager_role = next((role for role in core_roles if role.name == 'Event Manager'), None)
    if not event_manager_role:
        event_manager_role = Role(name='Event Manager')
        db_session.add(event_manager_role)
        db_session.commit()
    
    member = FullMemberFactory.create(
        firstname='Event',
        lastname='Manager',
        password='managerpassword123'
    )
    member.roles = [event_manager_role]
    db_session.add(member)
    db_session.commit()
    return member


@pytest.fixture
def content_manager_member(db_session, core_roles):
    """Create a member with Content Manager role."""
    content_manager_role = next((role for role in core_roles if role.name == 'Content Manager'), None)
    if not content_manager_role:
        content_manager_role = Role(name='Content Manager')
        db_session.add(content_manager_role)
        db_session.commit()
    
    member = FullMemberFactory.create(
        firstname='Content',
        lastname='Manager',
        password='managerpassword123'
    )
    member.roles = [content_manager_role]
    db_session.add(member)
    db_session.commit()
    return member