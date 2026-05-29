import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class EventLog(Base):
    """A log table that will get large and be used to generate query load."""

    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    event_type = Column(String(50), index=True)
    duration_ms = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def __repr__(self) -> str:
        return f"<EventLog(id={self.id}, type='{self.event_type}', ms={self.duration_ms})>"
