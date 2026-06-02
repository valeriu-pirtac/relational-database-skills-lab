from functools import lru_cache

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from app.config import (
    get_direct_db_uri,
    get_session_bouncer_uri,
    get_transaction_bouncer_uri,
)
from app.models import Base


@lru_cache(maxsize=1)
def get_direct_engine():
    """Singleton engine for direct PostgreSQL connections."""
    return create_engine(
        get_direct_db_uri(),
        echo=False,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_session_bouncer_engine():
    """Singleton engine for PgBouncer Session mode connections."""
    return create_engine(
        get_session_bouncer_uri(),
        echo=False,
        pool_pre_ping=True,
        poolclass=NullPool,
    )


def get_transaction_bouncer_engine(disable_prepared: bool = True):
    """
    Returns an engine for PgBouncer Transaction mode connections.
    If disable_prepared is True, it disables psycopg3's prepared statements
    by passing prepare_threshold=None in connect_args.
    """
    connect_args: dict[str, int | None] = {}
    if disable_prepared:
        connect_args["prepare_threshold"] = None

    return create_engine(
        get_transaction_bouncer_uri(),
        echo=False,
        pool_pre_ping=True,
        connect_args=connect_args,
        poolclass=NullPool,
    )


def init_db():
    """
    Initializes/resets the database schema.
    Always connect directly to the primary database to perform DDL.
    """
    engine = get_direct_engine()
    logger.info("[InitDB] Dropping and recreating tables directly on PostgreSQL...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.info("[InitDB] Database tables initialized successfully.")
