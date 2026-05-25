from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_db_uri
from app.models import Base, User


@lru_cache(maxsize=1)
def get_db_engine():
    """
    Creates and returns a singleton SQLAlchemy engine for the PostgreSQL database.
    Uses lru_cache to ensure only one engine instance is created per application lifecycle.
    """
    return create_engine(
        get_db_uri(),
        echo=False,  # Set to True if you want to see all underlying SQL queries emitted by SQLAlchemy
        pool_pre_ping=True,
    )


def get_session_factory():
    """
    Creates and returns a SQLAlchemy session factory for the PostgreSQL database.
    """
    return sessionmaker(autocommit=False, autoflush=False, bind=get_db_engine())


@contextmanager
def get_db_session():
    """Context manager / helper to manage session lifecycle."""
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def init_db():
    """Utility to reset the database tables for a clean slate."""
    engine = get_db_engine()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def insert_user(username, balance):
    """Helper function to insert a user into the database."""
    with get_db_session() as session:
        user = User(username=username, balance=balance)
        session.add(user)
        session.commit()
