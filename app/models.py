from datetime import datetime, timezone, date
from typing import Optional
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy import Table, Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db
from app import login

# Association table for many-to-many relationship
member_roles = Table(
    'member_roles',
    db.Model.metadata,
    Column('member_id', Integer, ForeignKey('member.id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True)
)

class Role(db.Model):
    __tablename__ = 'roles'

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)

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
    roles = relationship('Role', secondary=member_roles, back_populates='members')

    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login.user_loader
def load_user(id):
    return db.session.get(Member, int(id))

Role.members = relationship('Member', secondary=member_roles, back_populates='roles')

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

class Booking(db.Model):
    __tablename__ = 'bookings'

    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    booking_date: so.Mapped[date] = so.mapped_column(sa.Date, nullable=False)
    session: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False)
    rink: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False)
    priority: so.Mapped[Optional[str]] = so.mapped_column(sa.String(50), nullable=True)

    def __repr__(self):
        return f"<Booking id={self.id}, date={self.booking_date}, session={self.session}, rink={self.rink}>"

