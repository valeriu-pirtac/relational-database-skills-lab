from datetime import datetime

from sqlalchemy import (
    ARRAY,
    CHAR,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSTZRANGE, UUID, ExcludeConstraint
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


# ==========================================
# Step 0 Models: Standard Data Types
# ==========================================


class StandardTypesDemo(Base):
    """
    Demonstrates standard PostgreSQL data types and their characteristics.
    """

    __tablename__ = "standard_types_demo"

    id = Column(Integer, primary_key=True, index=True)
    small_int = Column(SmallInteger)
    big_int = Column(Integer)  # mapped to standard INT/BIGINT
    float_val = Column(Float)  # Inexact, double precision float
    numeric_val = Column(Numeric(10, 2))  # Exact numeric/decimal precision
    char_fixed = Column(CHAR(10))  # Fixed-length character representation
    varchar_var = Column(String(100))  # Variable-length character representation
    text_val = Column(Text)  # Unlimited variable-length text representation
    created_at = Column(DateTime, default=datetime.utcnow)


# ==========================================
# Step 1 Models: JSONB vs. Normalization
# ==========================================


class ProductRelational(Base):
    """
    Normalized Product table with explicit columns.
    """

    __tablename__ = "products_relational"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    price = Column(Integer, nullable=False)  # in cents
    brand = Column(String(100))
    color = Column(String(50))
    weight_kg = Column(Float)
    active = Column(DateTime, default=datetime.utcnow)


class ProductEAV(Base):
    """
    Product table using Entity-Attribute-Value pattern.
    """

    __tablename__ = "products_eav"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    price = Column(Integer, nullable=False)

    # Relationship to EAV attributes table
    attributes = relationship("ProductEAVAttribute", back_populates="product", cascade="all, delete-orphan")


class ProductEAVAttribute(Base):
    """
    Attributes mapping table for ProductEAV.
    """

    __tablename__ = "product_eav_attributes"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products_eav.id", ondelete="CASCADE"), nullable=False)
    key = Column(String(100), nullable=False, index=True)
    value = Column(Text, nullable=False)

    product = relationship("ProductEAV", back_populates="attributes")


class ProductJSONB(Base):
    """
    Product table storing flexible attributes in a JSONB column.
    """

    __tablename__ = "products_jsonb"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    price = Column(Integer, nullable=False)
    attributes = Column(JSONB)  # GIN-indexed flexible storage


# ==========================================
# Step 2 Models: UUIDv4 vs. UUIDv7
# ==========================================


class LogUUIDv4(Base):
    """
    Simulates high-throughput logging using standard random UUIDv4 primary keys.
    """

    __tablename__ = "logs_uuidv4"

    id = Column(UUID(as_uuid=True), primary_key=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class LogUUIDv7(Base):
    """
    Simulates high-throughput logging using time-ordered sequential UUIDv7 primary keys.
    """

    __tablename__ = "logs_uuidv7"

    id = Column(UUID(as_uuid=True), primary_key=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ==========================================
# Step 3 Models: Specialized Types (Arrays & Ranges)
# ==========================================


class RoomBooking(Base):
    """
    Booking system using arrays (text[]) and temporal ranges (tstzrange).
    Implements a database-level exclusion constraint to prevent double-booking.
    """

    __tablename__ = "room_bookings"

    id = Column(Integer, primary_key=True)
    room_name = Column(String(100), nullable=False)

    # Range of timestamps with timezones
    booking_period = Column(TSTZRANGE, nullable=False)

    # Array of strings to store amenities/tags
    amenities = Column(ARRAY(String), nullable=False)

    __table_args__ = (
        # Exclusion Constraint: Prevent overlapping bookings (&&) for the same room (=)
        ExcludeConstraint(
            ("room_name", "="),
            ("booking_period", "&&"),
            name="exclude_overlapping_room_bookings",
            using="gist",
        ),
    )

    def __repr__(self) -> str:
        return f"<RoomBooking(id={self.id}, room_name='{self.room_name}', period={self.booking_period})>"
