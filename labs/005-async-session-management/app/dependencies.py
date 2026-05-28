import logging
import threading
from collections.abc import AsyncGenerator

from loguru import logger
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import ASYNC_DATABASE_URL, DATABASE_URL


# Disable default SQLAlchemy logging to control logs via loguru
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# Sync database setup (for initialization)
engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=10, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Async database setup (FastAPI)
async_engine = create_async_engine(ASYNC_DATABASE_URL, pool_size=5, max_overflow=10, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)


def get_session_factory():
    """Returns the database session factory."""
    return SessionLocal


# Global query counter thread-safe helper
class QueryCounter:
    def __init__(self):
        self._count = 0
        self._lock = threading.Lock()
        self._log_queries = False

    def reset(self) -> None:
        with self._lock:
            self._count = 0

    def increment(self) -> None:
        with self._lock:
            self._count += 1

    @property
    def count(self) -> int:
        with self._lock:
            return self._count

    def enable_logging(self, enable: bool = True) -> None:
        with self._lock:
            self._log_queries = enable

    @property
    def is_logging_enabled(self) -> bool:
        with self._lock:
            return self._log_queries


query_counter = QueryCounter()


# Event listener to count and selectively log executed queries
def register_query_listeners(target_engine):
    @event.listens_for(target_engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        query_counter.increment()
        if query_counter.is_logging_enabled:
            # Shorten statements for cleaner logs
            cleaned_stmt = " ".join(statement.split())
            if len(cleaned_stmt) > 120:
                cleaned_stmt = cleaned_stmt[:117] + "..."
            logger.debug(f"[SQL Executed] {cleaned_stmt}")


register_query_listeners(engine)
register_query_listeners(async_engine.sync_engine)


def init_db() -> None:
    """Create all tables. Import models here to register them with metadata."""
    from app.models import Base

    # Drop all first for a clean standalone run
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.info("[Database] Dropped and re-created all tables.")


async def get_async_session() -> AsyncGenerator[AsyncSession]:
    """
    CORRECT: FastAPI async dependency yielding request-scoped session.
    A fresh session is created per request, and closed cleanly at the end.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Globally shared leaked session singleton
_leaked_session = None
_leaked_session_lock = threading.Lock()


async def get_leaked_session() -> AsyncSession:
    """
    INCORRECT/LEAKED: Yields a globally shared singleton AsyncSession.
    This simulates bad practices where developers share a session globally
    or register it as a singleton in a dependency injection container.
    """
    global _leaked_session
    with _leaked_session_lock:
        if _leaked_session is None:
            _leaked_session = AsyncSessionLocal()
    return _leaked_session
