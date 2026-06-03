from sqlalchemy import Column, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class DiagnosticItem(Base):
    """Simple model for executing heavy database queries."""

    __tablename__ = "diagnostic_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    value = Column(Float, default=0.0)

    def __repr__(self) -> str:
        return f"<DiagnosticItem(id={self.id}, name='{self.name}', value={self.value})>"
