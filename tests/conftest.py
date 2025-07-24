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