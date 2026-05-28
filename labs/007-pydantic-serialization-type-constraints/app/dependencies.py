import logging
from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import ASYNC_DATABASE_URL, DATABASE_URL


# Disable default SQLAlchemy logging to manage cleanly
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# Default base engines
default_sync_engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
)
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=default_sync_engine)

default_async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(
    bind=default_async_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """
    FastAPI dependency that yields an independent database session for each request,
    guaranteeing transaction boundaries and preventing session leakage.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def init_db() -> None:
    """Drops and re-creates database tables using the default sync engine."""
    from loguru import logger

    from app.models import Base

    Base.metadata.drop_all(bind=default_sync_engine)
    Base.metadata.create_all(bind=default_sync_engine)
    logger.success("[Database] Base tables successfully initialized.")
