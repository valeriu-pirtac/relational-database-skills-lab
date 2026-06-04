from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_db_uri
from app.models import Base


default_sync_engine = create_engine(
    get_db_uri(),
    echo=False,  # We'll rely on our own logging
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=default_sync_engine)


def init_db() -> None:
    """Drops and recreates all tables."""
    logger.info("[Database] Initializing base tables...")
    Base.metadata.drop_all(bind=default_sync_engine)
    Base.metadata.create_all(bind=default_sync_engine)
    logger.info("[Database] Tables created successfully.")
