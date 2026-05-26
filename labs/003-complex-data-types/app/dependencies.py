from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import get_db_uri
from app.models import Base


@lru_cache(maxsize=1)
def get_db_engine():
    """
    Creates and returns a singleton SQLAlchemy engine.
    Uses lru_cache to ensure only one engine instance per application lifecycle.
    """
    return create_engine(
        get_db_uri(),
        echo=False,  # Set to True to see SQL queries
        pool_pre_ping=True,
    )


def get_session_factory():
    """
    Creates and returns a SQLAlchemy session factory.
    """
    return sessionmaker(autocommit=False, autoflush=False, bind=get_db_engine())


@contextmanager
def get_db_session():
    """Context manager for database session lifecycle."""
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def init_db():
    """Initialize database tables (drops and recreates all tables)."""
    engine = get_db_engine()

    # Enable btree_gist extension required for composite exclusion constraints
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist;"))
        conn.commit()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
