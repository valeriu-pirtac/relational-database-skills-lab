from functools import lru_cache

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_db_uri
from app.models import Account, Base, Job


@lru_cache(maxsize=1)
def get_db_engine():
    """
    Creates and returns a singleton SQLAlchemy engine.
    """
    return create_engine(
        get_db_uri(),
        echo=False,
        pool_pre_ping=True,
    )


def get_session_factory():
    """
    Creates and returns a SQLAlchemy session factory.
    """
    return sessionmaker(autocommit=False, autoflush=False, bind=get_db_engine())


def init_db():
    """Utility to reset/initialize database tables and seed test data."""
    engine = get_db_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.info("[Database] Recreated tables (accounts, jobs).")

    session_factory = get_session_factory()
    with session_factory() as session:
        with session.begin():
            # Seed 2 Accounts for deadlock testing
            account1 = Account(name="Alice", balance=100.00)
            account2 = Account(name="Bob", balance=100.00)
            session.add_all([account1, account2])

            # Seed 10 Jobs for SKIP LOCKED testing
            jobs = [Job(payload=f"Task Payload #{i}") for i in range(1, 11)]
            session.add_all(jobs)

    logger.info("[Database] Seeded 2 accounts and 10 jobs.")
