from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_db_uri
from app.models import Base


default_sync_engine = create_engine(get_db_uri(), echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=default_sync_engine)


def init_db() -> None:
    logger.info("[Database] Initializing tables for Full-Text Search...")
    Base.metadata.drop_all(bind=default_sync_engine)
    Base.metadata.create_all(bind=default_sync_engine)
    logger.info("[Database] 'articles' table created with a generated TSVECTOR column and GIN index.")
