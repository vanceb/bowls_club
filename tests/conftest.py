"""
Test configuration and fixtures for the Bowls Club application.
"""
import pytest
import tempfile
import os
from app import create_app, db
from app.models import Member, Role

# Set environment variables for testing
os.environ['SECRET_KEY'] = 'test-secret-key-for-testing-only'
os.environ['MAIL_SUPPRESS_SEND'] = 'true'


@pytest.fixture(scope='session')
def app():
    """Create application for testing."""
    app = create_app('testing')
    
    # Create application context
    with app.app_context():
        yield app


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
        # Create all tables
        db.create_all()
        
        # Provide the session
        yield db.session
        
        # Clean up
        db.session.remove()
        db.drop_all()


@pytest.fixture
def core_roles(db_session):
    """Create core roles for testing."""
    roles = []
    for role_name in ['User Manager', 'Content Manager', 'Event Manager']:
        role = Role(name=role_name)
        db_session.add(role)
        roles.append(role)
    
    db_session.commit()
    return roles


@pytest.fixture
def test_member(db_session):
    """Create a basic test member."""
    member = Member(
        username='testuser',
        firstname='Test',
        lastname='User', 
        email='test@example.com',
        phone='123-456-7890',
        status='Full'
    )
    member.set_password('testpassword123')
    db_session.add(member)
    db_session.commit()
    return member


@pytest.fixture
def admin_member(db_session, core_roles):
    """Create an admin test member with all roles."""
    member = Member(
        username='admin',
        firstname='Admin',
        lastname='User',
        email='admin@example.com', 
        phone='123-456-7890',
        status='Full',
        is_admin=True
    )
    member.set_password('adminpassword123')
    member.roles = core_roles  # Assign all core roles
    db_session.add(member)
    db_session.commit()
    return member


@pytest.fixture
def pending_member(db_session):
    """Create a pending member for testing."""
    member = Member(
        username='pendinguser',
        firstname='Pending',
        lastname='User',
        email='pending@example.com',
        phone='123-456-7890',
        status='Pending'
    )
    member.set_password('pendingpassword123')
    db_session.add(member)
    db_session.commit()
    return member


@pytest.fixture
def user_manager_member(db_session, core_roles):
    """Create a member with User Manager role."""
    user_manager_role = next(role for role in core_roles if role.name == 'User Manager')
    member = Member(
        username='usermanager',
        firstname='User',
        lastname='Manager',
        email='usermanager@example.com',
        phone='123-456-7890',
        status='Full'
    )
    member.set_password('managerpassword123')
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
def test_event(db_session):
    """Create a test event."""
    from datetime import datetime, timedelta
    event = Event(
        name='Test Event',
        event_date=datetime.now() + timedelta(days=7),
        event_type=1,
        gender=1,
        format=1,
        has_pool=False
    )
    db_session.add(event)
    db_session.commit()
    return event


@pytest.fixture
def test_event_with_pool(db_session, test_event):
    """Create a test event with pool."""
    pool = Pool(event_id=test_event.id, is_open=True)
    test_event.has_pool = True
    db_session.add(pool)
    db_session.commit()
    test_event.pool = pool
    return test_event


@pytest.fixture
def test_pool(db_session, test_event):
    """Create a test pool."""
    pool = Pool(event_id=test_event.id, is_open=True)
    db_session.add(pool)
    db_session.commit()
    return pool


@pytest.fixture
def test_booking(db_session, test_event):
    """Create a test booking."""
    from datetime import datetime, timedelta
    booking = Booking(
        date=datetime.now() + timedelta(days=1),
        time_slot='Morning',
        event_id=test_event.id,
        status='Open'
    )
    db_session.add(booking)
    db_session.commit()
    return booking


@pytest.fixture
def event_manager_member(db_session, core_roles):
    """Create a member with Event Manager role."""
    event_manager_role = next((role for role in core_roles if role.name == 'Event Manager'), None)
    if not event_manager_role:
        event_manager_role = Role(name='Event Manager')
        db_session.add(event_manager_role)
        db_session.commit()
    
    member = Member(
        username='eventmanager',
        firstname='Event',
        lastname='Manager',
        email='eventmanager@example.com',
        phone='123-456-7890',
        status='Full'
    )
    member.set_password('managerpassword123')
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
    
    member = Member(
        username='contentmanager',
        firstname='Content',
        lastname='Manager',
        email='contentmanager@example.com',
        phone='123-456-7890',
        status='Full'
    )
    member.set_password('managerpassword123')
    member.roles = [content_manager_role]
    db_session.add(member)
    db_session.commit()
    return member