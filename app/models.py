from datetime import datetime, timezone, date
from typing import Optional
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db
from app import login

class Member(UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True,
                                                unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True,
                                             unique=True)
    phone: so.Mapped[str] = so.mapped_column(sa.String(15), index=True)
    firstname: so.Mapped[str] = so.mapped_column(sa.String(64))
    lastname: so.Mapped[str] = so.mapped_column(sa.String(64))
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    bookings: so.WriteOnlyMapped['Booking'] = so.relationship(back_populates='member')

    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login.user_loader
def load_user(id):
    return db.session.get(Member, int(id))


class Booking(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    member_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey(Member.id), index=True)
    member: so.Mapped[Member] = so.relationship('Member', back_populates='bookings')
    timestamp: so.Mapped[datetime] = so.mapped_column(sa.DateTime, index=True, default=datetime.now(timezone.utc))
    date: so.Mapped[datetime] = so.mapped_column(sa.DateTime, index=True)
    time: so.Mapped[str] = so.mapped_column(sa.String(5))
    duration: so.Mapped[int] = so.mapped_column(sa.Integer)
    notes: so.Mapped[Optional[str]] = so.mapped_column(sa.String(140))
    
    def __repr__(self):
        return '<Booking {}>'.format(self.id)