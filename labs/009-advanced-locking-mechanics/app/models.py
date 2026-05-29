from sqlalchemy import Column, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Account(Base):
    """Model for demonstrating FOR UPDATE and Deadlocks."""

    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    balance = Column(Numeric(10, 2), nullable=False, default=0.00)

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, name='{self.name}', balance={self.balance})>"


class Job(Base):
    """Model for demonstrating SKIP LOCKED queue processing."""

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    payload = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending, processing, completed

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, status='{self.status}')>"
