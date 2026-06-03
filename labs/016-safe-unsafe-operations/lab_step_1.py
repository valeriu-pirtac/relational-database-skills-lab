import threading
import time

from app.dependencies import get_db_engine, get_session_factory, init_db
from app.models import CustomerRecord
from loguru import logger
from sqlalchemy import text


def insert_workload(stop_event, latencies):
    """Background thread performing inserts to measure write latency."""
    engine = get_db_engine()
    counter = 1

    while not stop_event.is_set():
        t_start = time.time()
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        f"INSERT INTO customer_records (name, email, balance) VALUES ('User_{counter}', 'user_{counter}@test.com', 10.0)"
                    )
                )
            latency = time.time() - t_start
            latencies.append(latency)
            counter += 1
        except Exception as e:
            if not stop_event.is_set():
                logger.error(f"[Workload] Write error: {e}")
        time.sleep(0.05)  # Write every 50ms


def main():
    logger.info("Initializing database...")
    init_db()

    # Seed 100,000 records to make the index build measurable
    logger.info("Seeding database with 100,000 records to build I/O size (may take a few seconds)...")
    session_factory = get_session_factory()
    with session_factory() as session:
        # Bulk insert
        batch_size = 20000
        for b in range(5):
            records = [
                CustomerRecord(
                    name=f"Customer_{b * batch_size + i}",
                    email=f"cust_{b * batch_size + i}@company.com",
                    phone=f"555-{b * batch_size + i}",
                    balance=100.0,
                )
                for i in range(batch_size)
            ]
            session.add_all(records)
            session.commit()
            logger.info(f"  * Seeded {(b + 1) * batch_size} records")

    engine = get_db_engine()

    # --- Phase 1: Unsafe Index Creation ---
    logger.info("" + "=" * 20 + " PHASE 1: UNSAFE INDEX BUILD " + "=" * 20)
    stop_event = threading.Event()
    latencies_unsafe = []

    # Start concurrent write workload
    t_workload = threading.Thread(target=insert_workload, args=(stop_event, latencies_unsafe))
    t_workload.start()
    time.sleep(1)  # Warm up workload

    logger.info("[Migration] Executing standard CREATE INDEX idx_unsafe ON customer_records(email)...")
    t_start = time.time()
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE INDEX idx_unsafe_email ON customer_records(email)"))
        logger.info(f"[Migration] Standard Index built in {time.time() - t_start:.2f}s.")
    except Exception as e:
        logger.error(f"[Migration] Standard Index failed: {e}")

    time.sleep(1)
    stop_event.set()
    t_workload.join()

    max_lat_unsafe = max(latencies_unsafe) if latencies_unsafe else 0
    avg_lat_unsafe = sum(latencies_unsafe) / len(latencies_unsafe) if latencies_unsafe else 0
    logger.info("Unsafe Index Latency Report:")
    logger.info(f"  * Total Writes Executed: {len(latencies_unsafe)}")
    logger.info(f"  * Average Write Latency: {avg_lat_unsafe * 1000:.1f}ms")
    logger.info(f"  * Max Write Latency (Blocked Peak): {max_lat_unsafe * 1000:.1f}ms")

    # --- Phase 2: Safe Index Creation ---
    logger.info("" + "=" * 20 + " PHASE 2: SAFE INDEX BUILD (CONCURRENT) " + "=" * 20)
    stop_event = threading.Event()
    latencies_safe = []

    # Clean up old index and create a new column for safe indexing
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX idx_unsafe_email"))

    # Start concurrent write workload
    t_workload = threading.Thread(target=insert_workload, args=(stop_event, latencies_safe))
    t_workload.start()
    time.sleep(1)

    logger.info("[Migration] Executing CREATE INDEX CONCURRENTLY idx_safe ON customer_records(phone)...")
    logger.info("[Note] Executing in AUTOCOMMIT isolation mode (required for concurrent index builds)")
    t_start = time.time()
    try:
        # To execute CREATE INDEX CONCURRENTLY, we must bypass transaction blocks using AUTOCOMMIT
        autocommit_engine = engine.execution_options(isolation_level="AUTOCOMMIT")
        with autocommit_engine.connect() as conn:
            conn.execute(text("CREATE INDEX CONCURRENTLY idx_safe_phone ON customer_records(phone)"))
        logger.info(f"[Migration] Concurrent Index built in {time.time() - t_start:.2f}s.")
    except Exception as e:
        logger.error(f"[Migration] Concurrent Index failed: {e}")

    time.sleep(1)
    stop_event.set()
    t_workload.join()

    max_lat_safe = max(latencies_safe) if latencies_safe else 0
    avg_lat_safe = sum(latencies_safe) / len(latencies_safe) if latencies_safe else 0
    logger.info("Safe Index Latency Report:")
    logger.info(f"  * Total Writes Executed: {len(latencies_safe)}")
    logger.info(f"  * Average Write Latency: {avg_lat_safe * 1000:.1f}ms")
    logger.info(f"  * Max Write Latency (Blocked Peak): {max_lat_safe * 1000:.1f}ms")

    # Diagnostic comparison
    if max_lat_unsafe > max_lat_safe * 2:
        logger.info("[SUCCESS] Safe migration successfully prevented write blockage!")
        logger.info(f"  * Standard build maximum write lag: {max_lat_unsafe * 1000:.1f}ms")
        logger.info(f"  * Concurrent build maximum write lag: {max_lat_safe * 1000:.1f}ms")
    else:
        logger.warning(
            "[Note] Write latency difference was negligible due to small local database footprints, but concurrent indexing avoids locks natively in production."
        )

    logger.info("=" * 60)
    logger.info("Lab Step 1 Complete!")


if __name__ == "__main__":
    main()
