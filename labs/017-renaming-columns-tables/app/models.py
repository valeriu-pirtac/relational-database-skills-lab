from sqlalchemy import Column, Integer, String, event
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class UserAccount(Base):
    """Model that represents the database table before and during expansion."""

    __tablename__ = "user_accounts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    phone = Column(String(50), nullable=True)
    phone_number = Column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<UserAccount(id={self.id}, username='{self.username}', phone='{self.phone}', phone_number='{self.phone_number}')>"


# Event listener to automate dual-writing during the transition/expand phase
@event.listens_for(UserAccount, "before_insert")
@event.listens_for(UserAccount, "before_update")
def dual_write_phone(mapper, connection, target):
    """Automatically dual-writes phone modifications to both columns."""
    if target.phone is not None and target.phone_number is None:
        target.phone_number = target.phone
    elif target.phone_number is not None and target.phone is None:
        target.phone = target.phone_number
    elif target.phone is not None and target.phone_number is not None:
        if target.phone != target.phone_number:
            # Prefer phone as the primary source during transition
            target.phone_number = target.phone
