from sqlalchemy import Column, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class UserAccount(Base):
    """Simple model to demonstrate database replication operations."""

    __tablename__ = "user_accounts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    balance = Column(Float, default=0.0)

    def __repr__(self) -> str:
        return f"<UserAccount(id={self.id}, username='{self.username}', balance={self.balance})>"
