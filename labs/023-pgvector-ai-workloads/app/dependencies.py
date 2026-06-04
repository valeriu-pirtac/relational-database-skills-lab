from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import get_db_uri
from app.models import Base


default_sync_engine = create_engine(get_db_uri(), echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=default_sync_engine)


def init_db() -> None:
    logger.info("[Database] Initializing tables for pgvector...")

    # Crucial: Install the pgvector extension into the database first
    with default_sync_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.drop_all(bind=default_sync_engine)
    Base.metadata.create_all(bind=default_sync_engine)
    logger.info("[Database] 'document_chunks' table created with a Vector column.")
