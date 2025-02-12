from datetime import datetime, timezone
from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class Member(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True,
                                                unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True,
                                             unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    bookings: so.WriteOnlyMapped['Booking'] = so.relationship(back_populates='member')

    def __repr__(self):
        return '<User {}>'.format(self.username)


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