"""
Lab Step 1: Row-Level Locks (Lost Updates & FOR UPDATE)

This script demonstrates what happens when two transactions attempt to read and modify
the exact same row concurrently without locks (Lost Update Anomaly), and how to fix
it using SELECT ... FOR UPDATE.
"""

import threading
import time
from decimal import Decimal

from app.dependencies import get_session_factory, init_db
from app.models import Account
from loguru import logger
from sqlalchemy import select


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


# A barrier to ensure both threads read at exactly the same time
sync_barrier = threading.Barrier(2)


def lost_update_worker(worker_id: int, amount: Decimal) -> None:
    """Simulates a naive read-modify-write without row locks."""
    session_factory = get_session_factory()
    with session_factory() as session:
        with session.begin():
            # 1. Read phase
            account = session.execute(select(Account).where(Account.id == 1)).scalar_one()
            logger.info(f"[Worker {worker_id}] Read balance: {account.balance}")

            # Synchronize so both workers have read the old balance before writing
            sync_barrier.wait()

            # 2. Compute and write
            new_balance = account.balance + amount
            time.sleep(0.1 * worker_id)  # Slight stagger on writes

            account.balance = new_balance
            logger.warning(f"[Worker {worker_id}] Updating balance to: {new_balance}")


def for_update_worker(worker_id: int, amount: Decimal) -> None:
    """Simulates a safe read-modify-write using FOR UPDATE."""
    session_factory = get_session_factory()
    with session_factory() as session:
        with session.begin():
            logger.info(f"[Worker {worker_id}] Attempting to lock row with FOR UPDATE...")
            # 1. Read phase WITH LOCK
            # with_for_update() adds "FOR UPDATE" to the SQL query
            account = session.execute(select(Account).where(Account.id == 1).with_for_update()).scalar_one()

            logger.success(f"[Worker {worker_id}] Lock acquired! Read balance: {account.balance}")

            # Simulate some processing time
            time.sleep(1.0)

            # 2. Compute and write
            new_balance = account.balance + amount
            account.balance = new_balance
            logger.success(f"[Worker {worker_id}] Updating balance to: {new_balance}")
            # Lock is released when transaction commits at the end of the block


def main() -> None:
    """Main entry point for this lab step."""
    logger.info("Initializing database...")
    init_db()

    session_factory = get_session_factory()

    # --- TEST 1: THE LOST UPDATE (No Locks) ---
    print_separator("TEST 1: THE LOST UPDATE (NO LOCKS)")
    with session_factory() as session:
        initial = session.get(Account, 1).balance
        logger.info(f"Initial balance of Account 1: {initial}")

    # Spawn 2 threads trying to add 50 concurrently
    t1 = threading.Thread(target=lost_update_worker, args=(1, Decimal("50.00")))
    t2 = threading.Thread(target=lost_update_worker, args=(2, Decimal("50.00")))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    with session_factory() as session:
        final = session.get(Account, 1).balance
        logger.error(f"Final balance of Account 1: {final} (Expected: 200.00)")
        logger.error("A Lost Update occurred! Worker 2 overwrote Worker 1's changes.")

    # Reset the balance for Test 2
    with session_factory() as session:
        with session.begin():
            account = session.get(Account, 1)
            account.balance = Decimal("100.00")

    # --- TEST 2: FOR UPDATE ---
    print_separator("TEST 2: PREVENTING LOST UPDATES (FOR UPDATE)")
    with session_factory() as session:
        initial = session.get(Account, 1).balance
        logger.info(f"Initial balance of Account 1: {initial}")

    # We do not use the barrier here because the lock itself provides synchronization
    t3 = threading.Thread(target=for_update_worker, args=(3, Decimal("50.00")))
    t4 = threading.Thread(target=for_update_worker, args=(4, Decimal("50.00")))

    t3.start()
    # Slight delay to ensure t3 hits the DB first
    time.sleep(0.1)
    t4.start()

    t3.join()
    t4.join()

    with session_factory() as session:
        final = session.get(Account, 1).balance
        logger.success(f"Final balance of Account 1: {final} (Expected: 200.00)")
        logger.success("Lost Update prevented! Worker 4 was forced to wait for Worker 3's lock.")

    logger.info("=" * 60)
    logger.info("Lab Step 1 Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
