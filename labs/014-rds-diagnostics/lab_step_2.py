import threading
import time

from app.dependencies import get_db_engine, get_session_factory, init_db
from app.models import DiagnosticItem
from loguru import logger
from sqlalchemy import text


def lock_holder_thread(barrier):
    """Acquires a row lock on row ID 1 and holds it to block others."""
    session_factory = get_session_factory()
    with session_factory() as session:
        # Get item
        _ = session.get(DiagnosticItem, 1)
        logger.info("[Lock Holder] Locking row ID 1 (FOR UPDATE)...")
        # Acquire row lock using SELECT FOR UPDATE
        session.execute(text("SELECT id FROM diagnostic_items WHERE id = 1 FOR UPDATE"))
        logger.info("[Lock Holder] Lock acquired! Holding lock for 8 seconds...")
        barrier.wait()  # Signal lock is acquired
        time.sleep(8)
        session.commit()  # Release lock
        logger.info("[Lock Holder] Transaction committed. Lock released!")


def lock_waiter_thread(thread_id, barrier):
    """Attempts to update the locked row, blocking until release."""
    barrier.wait()  # Wait for holder to lock
    time.sleep(0.5)  # Ensure holder gets lock first
    logger.info(f"[Lock Waiter {thread_id}] Attempting update on row ID 1 (will block)...")

    session_factory = get_session_factory()
    with session_factory() as session:
        try:
            # This query will block until the lock holder commits
            session.execute(text("UPDATE diagnostic_items SET value = value + 1 WHERE id = 1"))
            session.commit()
            logger.info(f"[Lock Waiter {thread_id}] Update completed successfully!")
        except Exception as e:
            logger.error(f"[Lock Waiter {thread_id}] Failed: {e}")


def cpu_burner_thread(stop_event):
    """Executes a CPU-intensive query in a loop to generate CPU load."""
    logger.info("[CPU Burner] Starting CPU-heavy queries loop...")
    engine = get_db_engine()

    # MD5 calculation over 1 million records
    heavy_sql = text(
        """
        SELECT COUNT(md5(s.i::text))
        FROM generate_series(1, 1000000) s(i);
        """
    )

    while not stop_event.is_set():
        try:
            with engine.connect() as conn:
                conn.execute(heavy_sql)
        except Exception as e:
            if not stop_event.is_set():
                logger.error(f"[CPU Burner] Query error: {e}")
            break


def main():
    logger.info("Initializing database...")
    init_db()

    session_factory = get_session_factory()
    with session_factory() as session:
        item = DiagnosticItem(id=1, name="shared_config", value=100.0)
        session.add(item)
        session.commit()
        logger.info("Seeded lock row: ID 1")

    logger.info("Starting concurrent workload simulation...")
    logger.info("Make sure you have lab_step_1.py running in another terminal window!")

    barrier = threading.Barrier(4)  # 1 holder + 3 waiters
    stop_event = threading.Event()

    threads = []

    # 1. Start CPU Burner
    cpu_thread = threading.Thread(target=cpu_burner_thread, args=(stop_event,))
    threads.append(cpu_thread)
    cpu_thread.start()

    # 2. Start Lock Holder
    holder_t = threading.Thread(target=lock_holder_thread, args=(barrier,))
    threads.append(holder_t)
    holder_t.start()

    # 3. Start Lock Waiters (which will block)
    for i in range(1, 4):
        waiter_t = threading.Thread(target=lock_waiter_thread, args=(i, barrier))
        threads.append(waiter_t)
        waiter_t.start()

    # Wait for execution
    logger.info("Workload running for 10 seconds. Check the Performance Insights terminal...")
    time.sleep(10)

    # Clean up
    logger.info("Stopping CPU Burner thread...")
    stop_event.set()

    for t in threads:
        t.join()

    logger.info("All workload threads completed.")


if __name__ == "__main__":
    main()
