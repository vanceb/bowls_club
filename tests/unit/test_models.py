"""
Unit tests for database models.
"""
import pytest
from datetime import datetime
from app.models import Member, Role
from tests.fixtures.factories import MemberFactory, RoleFactory


@pytest.mark.unit
class TestMember:
    """Test cases for Member model."""
    
    def test_member_creation(self, db_session):
        """Test basic member creation."""
        member = MemberFactory.create(
            username='testuser',
            firstname='Test',
            lastname='User',
            email='test@example.com',
            phone='123-456-7890'
        )
        
        assert member.id is not None
        assert member.username == 'testuser'
        assert member.firstname == 'Test'
        assert member.lastname == 'User'
        assert member.email == 'test@example.com'
        assert member.phone == '123-456-7890'
        assert member.status == 'Pending'  # Default status
        assert member.is_admin is False
        assert member.share_email is True
        assert member.share_phone is True
    
    def test_password_hashing(self, db_session):
        """Test password hashing and verification."""
        member = MemberFactory.create(
            username='testuser', 
            firstname='Test',
            lastname='User',
            email='test@example.com'
        )
        member.set_password('mypassword123')
        db_session.add(member)
        db_session.commit()
        
        # Check password is hashed (not stored in plain text)
        assert member.password_hash != 'mypassword123'
        assert member.password_hash is not None
        
        # Check password verification
        assert member.check_password('mypassword123') is True
        assert member.check_password('wrongpassword') is False
        assert member.check_password('') is False
        assert member.check_password(None) is False
    
    def test_member_roles(self, db_session):
        """Test member role assignment."""
        member = MemberFactory.create(
            username='testuser', 
            firstname='Test',
            lastname='User',
            email='test@example.com'
        )
        role1 = RoleFactory.create(name='Test Role 1')  
        role2 = RoleFactory.create(name='Test Role 2')
        
        db_session.add_all([member, role1, role2])
        db_session.commit()
        
        # Test role assignment
        member.roles.append(role1)
        member.roles.append(role2)
        db_session.commit()
        
        assert len(member.roles) == 2
        assert role1 in member.roles
        assert role2 in member.roles
        
        # Test has_role method
        assert member.has_role('Test Role 1') is True
        assert member.has_role('Test Role 2') is True
        assert member.has_role('Nonexistent Role') is False
    
    def test_member_repr(self, db_session):
        """Test member string representation."""
        member = MemberFactory.create(
            username='testuser',
            firstname='Test',
            lastname='User', 
            email='test@example.com'
        )
        
        assert '<Member testuser>' in repr(member)
    
    def test_bootstrap_mode(self, db_session):
        """Test bootstrap mode detection."""
        # Should be True when no members exist
        assert Member.is_bootstrap_mode() is True
        
        # Should be False when members exist
        member = MemberFactory.create(
            username='testuser',
            firstname='Test',
            lastname='User',
            email='test@example.com'
        )
        
        assert Member.is_bootstrap_mode() is False
    
    def test_member_factory(self, db_session):
        """Test member factory."""
        member = MemberFactory()
        
        assert member.id is not None
        assert member.username is not None
        assert member.firstname is not None
        assert member.lastname is not None
        assert member.email is not None
        assert member.phone is not None
        assert member.check_password('defaultpassword123') is True


@pytest.mark.unit
class TestRole:
    """Test cases for Role model."""
    
    def test_role_creation(self, db_session):
        """Test basic role creation."""
        role = RoleFactory.create(name='Test Role')
        
        assert role.id is not None
        assert role.name == 'Test Role'
    
    def test_role_members_relationship(self, db_session):
        """Test role-member relationship."""
        role = RoleFactory.create(name='Test Role')
        member1 = MemberFactory.create(
            username='user1', 
            firstname='User',
            lastname='One',
            email='user1@example.com'
        )
        member2 = MemberFactory.create(
            username='user2',
            firstname='User', 
            lastname='Two',
            email='user2@example.com'
        )
        
        db_session.add_all([role, member1, member2])
        db_session.commit()
        
        # Assign role to members
        member1.roles.append(role)
        member2.roles.append(role)
        db_session.commit()
        
        # Test reverse relationship
        assert len(role.members) == 2
        assert member1 in role.members
        assert member2 in role.members
    
    def test_role_repr(self, db_session):
        """Test role string representation."""
        role = RoleFactory.create(name='Test Role')
        
        assert '<Role Test Role>' in repr(role)
    
    def test_role_factory(self, db_session):
        """Test role factory."""
        role = RoleFactory()
        
        assert role.id is not None
        assert role.name is not None
        assert 'Test Role' in role.name