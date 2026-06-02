from contextlib import contextmanager
from functools import lru_cache

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_primary_db_uri, get_replica_db_uri
from app.models import Base


@lru_cache(maxsize=1)
def get_primary_engine():
    """Singleton primary engine (writer)."""
    return create_engine(
        get_primary_db_uri(),
        echo=False,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_replica_engine():
    """Singleton replica engine (reader)."""
    return create_engine(
        get_replica_db_uri(),
        echo=False,
        pool_pre_ping=True,
    )


class RoutingSession(Session):
    """
    Subclass of SQLAlchemy Session that dynamically routes queries:
    - Writes and flushing are sent to the Primary database.
    - SELECT queries (reads) are routed to the Replica database.
    """

    def get_bind(self, mapper=None, clause=None, **kw):
        primary_eng = get_primary_engine()
        replica_eng = get_replica_engine()

        # 1. If flushing changes, route to Primary
        if self._flushing:
            logger.debug("[RoutingSession] Routing flush to Primary (Write)")
            return primary_eng

        # 2. Check statement clause
        if clause is not None:
            is_select = getattr(clause, "is_select", False)
            if is_select:
                logger.debug("[RoutingSession] Routing SELECT statement to Replica (Read)")
                return replica_eng
            else:
                logger.debug("[RoutingSession] Routing state-altering statement to Primary (Write)")
                return primary_eng

        # 3. Default fallback to Primary
        logger.debug("[RoutingSession] Defaulting bind to Primary")
        return primary_eng


def get_routing_session_factory():
    """Returns a sessionmaker configured with the custom RoutingSession."""
    return sessionmaker(class_=RoutingSession, expire_on_commit=False)


@contextmanager
def get_routing_session():
    """Context manager for routing session lifecycle."""
    factory = get_routing_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def init_db():
    """
    Initializes/resets tables.
    CRITICAL: DDL operations (CREATE/DROP TABLE) must ONLY run on the primary engine.
    They will automatically replicate to the replica via physical replication.
    """
    engine = get_primary_engine()
    logger.info("[InitDB] Dropping and creating tables on Primary...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.info("[InitDB] Database tables initialized on Primary.")
