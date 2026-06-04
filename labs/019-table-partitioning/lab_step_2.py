"""
Lab Step 2: Dynamic Lifecycle (Attach/Detach)
"""

from datetime import datetime

from app.dependencies import SessionLocal, default_sync_engine
from app.models import SensorData
from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def main():
    print_separator("PHASE 1: TRIGGERING A PARTITION ROUTING ERROR")
    with SessionLocal() as session:
        logger.warning("[App] Attempting to insert an April record into 'sensor_data'...")

        try:
            session.add(SensorData(id=4, timestamp=datetime(2023, 4, 15), device_id="D3", temperature=24.0))
            session.commit()
        except DBAPIError as e:
            logger.error("[Database Error] Insert failed! PostgreSQL could not route the row.")
            logger.error(f"[Error Details] {e.orig}")
            session.rollback()

        print_separator("PHASE 2: DYNAMICALLY ATTACHING A NEW PARTITION")
        logger.warning("[Database] Creating 'sensor_data_apr' partition...")
        session.execute(
            text(
                "CREATE TABLE sensor_data_apr PARTITION OF sensor_data FOR VALUES FROM ('2023-04-01') TO ('2023-05-01')"
            )
        )
        session.commit()

        logger.success("[App] Re-attempting the April insert...")
        session.add(SensorData(id=4, timestamp=datetime(2023, 4, 15), device_id="D3", temperature=24.0))
        session.commit()
        logger.success("[Success] The April data was successfully routed!")

    print_separator("PHASE 3: ZERO-BLOAT DATA ARCHIVAL (DETACH)")
    # DDL operations like DETACH PARTITION are best run with AUTOCOMMIT so they don't hold transaction locks unnecessarily long
    with default_sync_engine.execution_options(isolation_level="AUTOCOMMIT").begin() as conn:
        logger.warning("[Database] Detaching the January partition ('sensor_data_jan') from the parent...")
        conn.execute(text("ALTER TABLE sensor_data DETACH PARTITION sensor_data_jan"))

    with SessionLocal() as session:
        logger.success("[Success] 'sensor_data_jan' is now a standalone table!")
        count = session.execute(text("SELECT COUNT(*) FROM sensor_data_jan")).scalar()
        logger.info(f"[Verification] The detached table still has its {count} record(s).")

        parent_count = session.execute(text("SELECT COUNT(*) FROM sensor_data")).scalar()
        logger.info(f"[Verification] The parent 'sensor_data' table now only has {parent_count} records.")
        logger.success(
            "[Observation] We instantly archived old data without running a DELETE statement, saving massive bloat!"
        )


if __name__ == "__main__":
    main()
