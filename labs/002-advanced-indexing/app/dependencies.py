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
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def execute_sql_file(filepath: str) -> None:
    """Execute SQL commands from a file."""
    engine = get_db_engine()
    with open(filepath) as f:
        sql_content = f.read()

    with engine.connect() as conn:
        # Split by semicolon and execute each statement
        statements = [s.strip() for s in sql_content.split(";") if s.strip()]
        for statement in statements:
            conn.execute(text(statement))
        conn.commit()
