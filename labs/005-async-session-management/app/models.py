from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for Declarative SQLAlchemy models."""

    pass


class User(Base):
    """Represents a platform user."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 1-to-Many relationship with BankAccount
    accounts = relationship("BankAccount", back_populates="user", cascade="all, delete-orphan")


class BankAccount(Base):
    """Represents a user's bank account with balance."""

    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    account_number = Column(String(20), unique=True, nullable=False, index=True)
    balance = Column(Numeric(12, 2), nullable=False, default=0.00)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Many-to-1 relationship with User (lazy loaded by default)
    user = relationship("User", back_populates="accounts")
