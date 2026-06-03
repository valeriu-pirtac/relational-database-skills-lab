from sqlalchemy import Column, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class CustomerRecord(Base):
    """Simple model to represent customer profiles in a high-traffic table."""

    __tablename__ = "customer_records"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False)
    phone = Column(String(50), nullable=True)
    balance = Column(Float, default=0.0)

    def __repr__(self) -> str:
        return f"<CustomerRecord(id={self.id}, name='{self.name}', email='{self.email}')>"
