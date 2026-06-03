import threading
import time

from app.dependencies import get_db_engine, get_session_factory, init_db
from app.models import CustomerRecord
from loguru import logger
from sqlalchemy import text


def insert_workload(stop_event, latencies):
    """Background thread executing updates to measure write latency during DDL."""
    engine = get_db_engine()
    counter = 1

    while not stop_event.is_set():
        t_start = time.time()
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(f"UPDATE customer_records SET balance = balance + 0.01 WHERE id = {(counter % 100000) + 1}")
                )
            latency = time.time() - t_start
            latencies.append(latency)
            counter += 1
        except Exception as e:
            if not stop_event.is_set():
                logger.error(f"[Workload] Write error: {e}")
        time.sleep(0.01)  # High-frequency write every 10ms


def main():
    logger.info("Initializing database...")
    init_db()

    # Seed 100,000 records
    logger.info("Seeding database with 100,000 records (may take a few seconds)...")
    session_factory = get_session_factory()
    with session_factory() as session:
        batch_size = 20000
        for b in range(5):
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

    # --- Phase 1: Unsafe Constraint Creation ---
    logger.info("" + "=" * 20 + " PHASE 1: UNSAFE CONSTRAINT ADDITION " + "=" * 20)
    stop_event = threading.Event()
    latencies_unsafe = []

    t_workload = threading.Thread(target=insert_workload, args=(stop_event, latencies_unsafe))
    t_workload.start()
    time.sleep(1)

    logger.info(
        "[Migration] Executing: ALTER TABLE customer_records ADD CONSTRAINT check_balance CHECK (balance >= 0)..."
    )
    t_start = time.time()
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE customer_records ADD CONSTRAINT check_balance CHECK (balance >= 0)"))
        logger.info(f"[Migration] Unsafe constraint added in {time.time() - t_start:.2f}s.")
    except Exception as e:
        logger.error(f"[Migration] Unsafe constraint failed: {e}")

    time.sleep(1)
    stop_event.set()
    t_workload.join()

    max_lat_unsafe = max(latencies_unsafe) if latencies_unsafe else 0
    avg_lat_unsafe = sum(latencies_unsafe) / len(latencies_unsafe) if latencies_unsafe else 0
    logger.info("Unsafe Constraint Latency Report:")
    logger.info(f"  * Average Write Latency: {avg_lat_unsafe * 1000:.1f}ms")
    logger.info(f"  * Max Write Latency (Blocked Peak): {max_lat_unsafe * 1000:.1f}ms")

    # --- Phase 2: Safe Constraint Creation (NOT VALID + VALIDATE) ---
    logger.info("=" * 20 + " PHASE 2: SAFE CONSTRAINT ADDITION (NOT VALID) " + "=" * 20)

    # Drop constraint
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE customer_records DROP CONSTRAINT check_balance"))

    stop_event = threading.Event()
    latencies_safe = []

    t_workload = threading.Thread(target=insert_workload, args=(stop_event, latencies_safe))
    t_workload.start()
    time.sleep(1)

    logger.info(
        "[Migration] Executing: ALTER TABLE customer_records ADD CONSTRAINT check_balance CHECK (balance >= 0) NOT VALID..."
    )
    t_start = time.time()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE customer_records ADD CONSTRAINT check_balance CHECK (balance >= 0) NOT VALID")
            )
        logger.info(
            f"[Migration] Step 1: Constraint added as NOT VALID in {time.time() - t_start:.4f}s (Instantaneous!)."
        )

        # Step 2: Validate constraint concurrently
        logger.info("[Migration] Executing: ALTER TABLE customer_records VALIDATE CONSTRAINT check_balance...")
        t_val_start = time.time()

        # Validation runs under ShareUpdateExclusiveLock (non-blocking)
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE customer_records VALIDATE CONSTRAINT check_balance"))
        logger.info(f"[Migration] Step 2: Constraint validated in {time.time() - t_val_start:.2f}s.")

    except Exception as e:
        logger.error(f"[Migration] Safe constraint failed: {e}")

    time.sleep(1)
    stop_event.set()
    t_workload.join()

    max_lat_safe = max(latencies_safe) if latencies_safe else 0
    avg_lat_safe = sum(latencies_safe) / len(latencies_safe) if latencies_safe else 0
    logger.info("Safe Constraint Latency Report:")
    logger.info(f"  * Average Write Latency: {avg_lat_safe * 1000:.1f}ms")
    logger.info(f"  * Max Write Latency (Blocked Peak): {max_lat_safe * 1000:.1f}ms")

    # Diagnostic comparison
    if max_lat_unsafe > max_lat_safe * 1.5:
        logger.info("[SUCCESS] Safe validation successfully prevented write blockage!")
        logger.info(f"  * Standard constraint maximum write lag: {max_lat_unsafe * 1000:.1f}ms")
        logger.info(f"  * NOT VALID constraint maximum write lag: {max_lat_safe * 1000:.1f}ms")

    logger.info("=" * 60)
    logger.info("Lab Step 2 Complete!")


if __name__ == "__main__":
    main()
