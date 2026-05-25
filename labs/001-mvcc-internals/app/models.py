from typing import Any

from sqlalchemy import Column, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, column_property
from sqlalchemy.orm.properties import ColumnProperty
from sqlalchemy.sql import column


# Declarative base class for db models
class Base(DeclarativeBase):
    pass


class User(Base):
    """User model to demonstrate Postgres system columns."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    balance = Column(Numeric(10, 2), nullable=False, default=100.00)

    # SQLAlchemy allows us to map system columns explicitly using column()
    # Note: These columns are managed by Postgres, we must set them to deferred or read-only.
    # We will map them here so you see how they can be retrieved directly via ORM models!
    xmin: ColumnProperty[Any] = column_property(column("xmin"))
    xmax: ColumnProperty[Any] = column_property(column("xmax"))
    ctid: ColumnProperty[Any] = column_property(column("ctid"))

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', balance={self.balance}, xmin={self.xmin}, xmax={self.xmax}, ctid='{self.ctid}')>"
