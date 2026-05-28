import logging

from loguru import logger
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import ASYNC_DATABASE_URL, DATABASE_URL


# Disable default SQLAlchemy logging to manage via loguru
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# Default base engines
default_sync_engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_timeout=30.0,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=default_sync_engine)


def register_pool_listeners(pool) -> None:
    """Registers connection pool event listeners for rich visibility into connection cycles."""

    @event.listens_for(pool, "connect")
    def on_connect(dbapi_connection, connection_record):
        logger.info("   [System Connect] Opened a BRAND NEW physical DB connection.")

    @event.listens_for(pool, "checkout")
    def on_checkout(dbapi_connection, connection_record, connection_proxy):
        logger.debug(f"   [Checkout] Connection checked out from pool. Active checkouts: {pool.checkedout()}")

    @event.listens_for(pool, "checkin")
    def on_checkin(dbapi_connection, connection_record):
        logger.debug("   [Checkin] Connection returned cleanly to pool.")


# Register pool listeners on the default engine's pool
register_pool_listeners(default_sync_engine.pool)


def get_custom_engine(
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_pre_ping: bool = True,
    pool_timeout: float = 30.0,
    is_async: bool = True,
):
    """
    Constructs and returns a custom engine (sync or async) with precise pool parameters,
    complete with event logging listeners.
    """
    if is_async:
        async_engine = create_async_engine(
            ASYNC_DATABASE_URL,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=pool_pre_ping,
            pool_timeout=pool_timeout,
        )
        register_pool_listeners(async_engine.sync_engine.pool)
        return async_engine
    else:
        sync_engine = create_engine(
            DATABASE_URL,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=pool_pre_ping,
            pool_timeout=pool_timeout,
        )
        register_pool_listeners(sync_engine.pool)
        return sync_engine


def init_db() -> None:
    """Drops and re-creates database tables using the default sync engine."""
    from app.models import Base

    Base.metadata.drop_all(bind=default_sync_engine)
    Base.metadata.create_all(bind=default_sync_engine)
    logger.success("[Database] Base tables successfully initialized.")
