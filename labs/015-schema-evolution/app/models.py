from sqlalchemy import Column, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Product(Base):
    """Simple model to represent a production catalog table."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(50), unique=True, nullable=False)
    price = Column(Numeric(10, 2), default=0.0)

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku='{self.sku}', price={self.price})>"
