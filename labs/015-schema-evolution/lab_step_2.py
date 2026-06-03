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

        barrier.wait()

        logger.info("[Lock Holder] Holding transaction open for 5 seconds...")
        time.sleep(5)
        session.commit()
        logger.info("[Lock Holder] Transaction committed (lock released).")


def migration_thread(barrier):
    """Runs DDL but sets a short lock_timeout constraint first."""
    barrier.wait()
    time.sleep(0.5)

    logger.info("[Migration] Running migration with lock_timeout = '1s'...")
    engine = get_db_engine()

    t_start = time.time()
    try:
        with engine.begin() as conn:
            # Set lock timeout for the current transaction
            conn.execute(text("SET lock_timeout = '1000'"))  # 1000ms = 1s
            conn.execute(text("ALTER TABLE products ADD COLUMN description VARCHAR(255)"))
        elapsed = time.time() - t_start
        logger.info(f"[Migration] DDL completed successfully in {elapsed:.2f}s!")
    except Exception as e:
        elapsed = time.time() - t_start
        logger.warning(f"[Migration] DDL FAILED as expected after {elapsed:.2f}s (Graceful Fail): {e}")


def api_reader_thread(barrier):
    """Simulates an API request doing a simple SELECT."""
    barrier.wait()
    time.sleep(1.0)

    logger.info("[API Reader] Attempting simple SELECT * FROM products...")
    engine = get_db_engine()

    t_start = time.time()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT * FROM products"))
        elapsed = time.time() - t_start
        logger.info(f"[API Reader] SELECT completed in {elapsed:.2f}s!")
        if elapsed < 1.5:
            logger.info(f"[Success] API Reader remained unaffected! Latency was only {elapsed:.4f}s.")
        else:
            logger.error(f"[Failure] API Reader was blocked for {elapsed:.2f}s!")
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

    logger.info("Starting DDL Block simulation with Lock Timeout (Step 2)...")

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
    logger.info("Lab Step 2 Complete!")


if __name__ == "__main__":
    main()
