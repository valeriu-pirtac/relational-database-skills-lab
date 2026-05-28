from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all Declarative ORM models."""

    pass


class Customer(Base):
    """Represents a store customer."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 1-to-Many relationship with Order
    orders: Mapped[list["Order"]] = relationship(back_populates="customer", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Customer(id={self.id}, email='{self.email}', status='{self.status}')>"


class Order(Base):
    """Represents a customer's purchase order."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    order_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Many-to-1 relationship with Customer
    customer: Mapped["Customer"] = relationship(back_populates="orders")

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, customer_id={self.customer_id}, amount={self.amount}, status='{self.status}')>"
