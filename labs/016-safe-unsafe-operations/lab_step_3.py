import time

from app.dependencies import get_db_engine, get_session_factory, init_db
from app.models import CustomerRecord
from loguru import logger
from sqlalchemy import text


def backfill_in_batches(batch_size: int = 20000):
    """Backfills the discount column in small chunks to avoid long lock durations."""
    engine = get_db_engine()

    # Find max ID
    with engine.connect() as conn:
        max_id = conn.execute(text("SELECT MAX(id) FROM customer_records")).scalar() or 0

    logger.info(f"Starting batch backfill for customer_records up to max ID: {max_id}")

    start_id = 1
    batch_count = 0

    while start_id <= max_id:
        end_id = start_id + batch_size
        t_start = time.time()

        # We update only records in the current ID range
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    UPDATE customer_records
                    SET discount = 0.0
                    WHERE id >= :start_id AND id < :end_id AND discount IS NULL
                    """
                ),
                {"start_id": start_id, "end_id": end_id},
            )
            rows_updated = result.rowcount

        elapsed = time.time() - t_start
        batch_count += 1
        logger.info(
            f"  * Batch {batch_count}: Updated IDs {start_id} to {end_id - 1} ({rows_updated} rows) in {elapsed * 1000:.1f}ms"
        )

        start_id = end_id
        # Throttling/Sleeping to release locks and allow concurrent queries to execute
        time.sleep(0.1)


def main():
    logger.info("Initializing database...")
    init_db()

    # Seed 100,000 records
    logger.info("Seeding database with 100,000 records...")
    session_factory = get_session_factory()
    with session_factory() as session:
        batch_size = 25000
        for b in range(4):
            records = [
                CustomerRecord(
                    name=f"Customer_{b * batch_size + i}",
                    email=f"cust_{b * batch_size + i}@company.com",
                    balance=100.0,
                )
                for i in range(batch_size)
            ]
            session.add_all(records)
            session.commit()
            logger.info(f"  * Seeded {(b + 1) * batch_size} records")

    engine = get_db_engine()

    # 1. Add column as nullable (Safe, instantaneous)
    logger.info("=" * 20 + " STEP 1: ADD COLUMN AS NULLABLE " + "=" * 20)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE customer_records ADD COLUMN discount FLOAT DEFAULT NULL"))
    logger.info("Column 'discount' added as NULLABLE.")

    # 2. Backfill in throttled batches (Safe, non-blocking)
    logger.info("=" * 20 + " STEP 2: THROTTLED BATCH BACKFILL " + "=" * 20)
    backfill_in_batches(batch_size=20000)
    logger.info("Batch backfill completed.")

    # 3. Add constraint as NOT VALID and validate (Safe, zero downtime)
    logger.info("=" * 20 + " STEP 3: ADD CONSTRAINT NOT VALID " + "=" * 20)
    with engine.begin() as conn:
        # We enforce NOT NULL using a CHECK constraint, initially NOT VALID
        conn.execute(
            text(
                """
                ALTER TABLE customer_records
                ADD CONSTRAINT discount_not_null CHECK (discount IS NOT NULL) NOT VALID
                """
            )
        )
    logger.info("Constraint 'discount_not_null' added as NOT VALID (instantaneous).")

    logger.info("=" * 20 + " STEP 4: VALIDATE CONSTRAINT CONCURRENTLY " + "=" * 20)
    t_start = time.time()
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE customer_records VALIDATE CONSTRAINT discount_not_null"))
    logger.info(f"Constraint validated successfully in {time.time() - t_start:.2f}s!")

    logger.info("=" * 60)
    logger.info("Lab Step 3 Complete!")


if __name__ == "__main__":
    main()
