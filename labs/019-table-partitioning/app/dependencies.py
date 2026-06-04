from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import get_db_uri
from app.models import Base


default_sync_engine = create_engine(get_db_uri(), echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=default_sync_engine)


def init_db() -> None:
    """Drops and recreates the partitioned schema."""
    logger.info("[Database] Initializing partitioned tables...")
    Base.metadata.drop_all(bind=default_sync_engine)
    Base.metadata.create_all(bind=default_sync_engine)

    # SQLAlchemy cannot dynamically create partitions via declarative Base yet.
    # We must explicitly create the child tables using raw SQL DDL.
    with default_sync_engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE sensor_data_jan PARTITION OF sensor_data FOR VALUES FROM ('2023-01-01') TO ('2023-02-01')"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE sensor_data_feb PARTITION OF sensor_data FOR VALUES FROM ('2023-02-01') TO ('2023-03-01')"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE sensor_data_mar PARTITION OF sensor_data FOR VALUES FROM ('2023-03-01') TO ('2023-04-01')"
            )
        )
    logger.info("[Database] Child partitions for Jan, Feb, Mar created.")
