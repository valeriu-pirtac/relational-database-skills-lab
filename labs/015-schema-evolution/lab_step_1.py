import threading
import time

from app.dependencies import get_db_engine, get_session_factory, init_db
from app.models import Product
from loguru import logger
from sqlalchemy import text


def lock_holder_thread(barrier):
    """Holds a read transaction lock (AccessShareLock) on the table."""
    session_factory = get_session_factory()
    with session_factory() as session:
        logger.info("[Lock Holder] Starting transaction and reading table...")
        session.execute(text("SELECT id FROM products"))

        # Signal that the transaction has started and read the table
        barrier.wait()

        logger.info("[Lock Holder] Holding transaction open for 5 seconds...")
        time.sleep(5)
        session.commit()
        logger.info("[Lock Holder] Transaction committed (lock released).")


def migration_thread(barrier):
    """Simulates a migration script running DDL (AccessExclusiveLock)."""
    barrier.wait()  # Wait for holder to acquire its lock
    time.sleep(0.5)  # Ensure holder lock is registered

    logger.info("[Migration] Running DDL: ALTER TABLE products ADD COLUMN description VARCHAR(255)...")
    engine = get_db_engine()

    t_start = time.time()
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE products ADD COLUMN description VARCHAR(255)"))
        elapsed = time.time() - t_start
        logger.info(f"[Migration] DDL completed successfully in {elapsed:.2f}s!")
    except Exception as e:
        elapsed = time.time() - t_start
        logger.error(f"[Migration] DDL failed after {elapsed:.2f}s: {e}")


def api_reader_thread(barrier):
    """Simulates an API request doing a simple SELECT."""
    barrier.wait()  # Wait for holder to acquire its lock
    time.sleep(1.0)  # Ensure migration enters lock queue first

    logger.info("[API Reader] Attempting simple SELECT * FROM products...")
    engine = get_db_engine()

    t_start = time.time()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT * FROM products"))
        elapsed = time.time() - t_start
        logger.info(f"[API Reader] SELECT completed in {elapsed:.2f}s!")
        if elapsed > 2.0:
            logger.error(f"[API Reader] CASCADING OUTAGE DETECTED! Simple read query was blocked for {elapsed:.2f}s!")
    except Exception as e:
        logger.error(f"[API Reader] SELECT failed: {e}")


def main():
    logger.info("Initializing database...")
    init_db()

    session_factory = get_session_factory()
    with session_factory() as session:
        prod = Product(sku="PROD-001", price=19.99)
        session.add(prod)
        session.commit()

    logger.info("Starting DDL Block simulation (Step 1)...")

    barrier = threading.Barrier(3)

    t_holder = threading.Thread(target=lock_holder_thread, args=(barrier,))
    t_migration = threading.Thread(target=migration_thread, args=(barrier,))
    t_reader = threading.Thread(target=api_reader_thread, args=(barrier,))

    t_holder.start()
    t_migration.start()
    t_reader.start()

    t_holder.join()
    t_migration.join()
    t_reader.join()

    logger.info("=" * 60)
    logger.info("Lab Step 1 Complete!")


if __name__ == "__main__":
    main()
