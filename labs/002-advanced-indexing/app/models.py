from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class Product(Base):
    """
    Product catalog with JSONB attributes.
    Demonstrates GIN indexing for JSONB columns and partial indexes.
    """

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(Text)
    price = Column(Integer, nullable=False)  # Price in cents
    active = Column(Boolean, default=True, nullable=False)
    attributes = Column(JSONB)  # Flexible attributes storage
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name='{self.name}', active={self.active})>"


class Article(Base):
    """
    Article/blog content with full-text search capabilities.
    Demonstrates GIN indexes for full-text search using tsvector.
    """

    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    author = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(JSONB)  # Array of tags
    published = Column(Boolean, default=False, nullable=False)
    search_vector = Column(TSVECTOR)  # Full-text search vector
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Article(id={self.id}, title='{self.title}', author='{self.author}')>"


class SensorReading(Base):
    """
    IoT sensor timeseries data with millions of rows.
    Demonstrates BRIN indexing for naturally ordered, massive datasets.
    """

    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True)
    sensor_id = Column(String(50), nullable=False)
    temperature = Column(Integer, nullable=False)  # Temperature * 100 (e.g., 2534 = 25.34°C)
    humidity = Column(Integer, nullable=False)  # Humidity * 100
    pressure = Column(Integer, nullable=False)  # Pressure in pascals
    location = Column(String(100), nullable=False)
    recorded_at = Column(DateTime, nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<SensorReading(id={self.id}, sensor_id='{self.sensor_id}', recorded_at={self.recorded_at})>"


class User(Base):
    """
    User accounts demonstrating expression indexes.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, unique=True)
    username = Column(String(100), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', username='{self.username}')>"
