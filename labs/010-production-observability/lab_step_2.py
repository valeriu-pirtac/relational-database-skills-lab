"""
Lab Step 2: Diagnosing Active Locks with pg_stat_activity

This script simulates a blocked transaction and uses pg_stat_activity
to diagnose exactly what query is blocking the application.
"""

import threading
import time

from app.dependencies import get_session_factory, init_db
from app.models import EventLog
from loguru import logger
from sqlalchemy import text


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def blocker_thread():
    """A thread that locks a row and goes to sleep, simulating a stalled transaction."""
    session_factory = get_session_factory()
    with session_factory() as session:
        logger.warning("[Blocker] Starting transaction and locking row ID 1...")
        # Acquire a row lock
        session.execute(text("SELECT * FROM event_logs WHERE id = 1 FOR UPDATE"))
        logger.warning("[Blocker] Row locked! Going to sleep for 5 seconds without committing...")
        time.sleep(5)
        logger.warning("[Blocker] Woke up. Committing transaction to release lock.")
        session.commit()


def blocked_thread():
    """A thread that tries to update the locked row and gets blocked."""
    session_factory = get_session_factory()
    with session_factory() as session:
        time.sleep(1)  # Wait for blocker to acquire lock
        logger.error("[Blocked] Attempting to update row ID 1...")
        # This will block until the blocker commits
        session.execute(text("UPDATE event_logs SET duration_ms = 999 WHERE id = 1"))
        session.commit()
        logger.error("[Blocked] Update successful! Lock was released.")


def diagnostic_thread():
    """A thread that queries pg_stat_activity to find the blocked query."""
    session_factory = get_session_factory()
    with session_factory() as session:
        time.sleep(2)  # Wait for deadlock scenario to occur
        print_separator("Diagnosing Active Locks via pg_stat_activity")

        # Query to find blocked queries and the queries blocking them
        query = text("""
            SELECT
                blocked_locks.pid AS blocked_pid,
                blocked_activity.query AS blocked_query,
                blocking_locks.pid AS blocking_pid,
                blocking_activity.query AS blocking_query
            FROM pg_catalog.pg_locks blocked_locks
            JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
            JOIN pg_catalog.pg_locks blocking_locks
                ON blocking_locks.locktype = blocked_locks.locktype
                AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
                AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
                AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
                AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
                AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
                AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
                AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
                AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
                AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
                AND blocking_locks.pid != blocked_locks.pid
            JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
            WHERE NOT blocked_locks.granted;
        """)

        results = session.execute(query).fetchall()

        if not results:
            logger.info("No blocked queries found.")
            return

        for row in results:
            logger.info(f"Blocked PID: {row.blocked_pid} | Query waiting: {row.blocked_query[:50]}")
            logger.info(f"Blocking PID: {row.blocking_pid} | Query holding lock: {row.blocking_query[:50]}")
            logger.info("-" * 40)

        logger.info("In production, you would run: SELECT pg_terminate_backend(<blocking_pid>); to kill the blocker.")


def main() -> None:
    """Main entry point for this lab step."""
    logger.info("Initializing database (if not already done)...")
    init_db()

    # Ensure there is a row with ID 1
    session_factory = get_session_factory()
    with session_factory() as session:
        if not session.query(EventLog).first():
            session.add(EventLog(user_id=1, event_type="test", duration_ms=10.0))
            session.commit()

    print_separator("STEP 2: Diagnosing Blocked Queries")

    # Start all threads
    t1 = threading.Thread(target=blocker_thread)
    t2 = threading.Thread(target=blocked_thread)
    t3 = threading.Thread(target=diagnostic_thread)

    t1.start()
    t2.start()
    t3.start()

    t1.join()
    t2.join()
    t3.join()

    print_separator("Lab Step 2 Complete!")


if __name__ == "__main__":
    main()
