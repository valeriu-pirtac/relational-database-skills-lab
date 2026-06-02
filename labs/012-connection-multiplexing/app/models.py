from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class InventoryItem(Base):
    """Simple model to demonstrate queries via connection multiplexing."""

    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    quantity = Column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<InventoryItem(id={self.id}, name='{self.name}', quantity={self.quantity})>"
