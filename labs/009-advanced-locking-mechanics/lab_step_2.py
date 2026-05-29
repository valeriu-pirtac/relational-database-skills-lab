"""
Lab Step 2: Deadlocks & Deterministic Ordering

This script demonstrates how deadlocks occur when two concurrent transactions attempt
to acquire locks on multiple resources in a different order. It then demonstrates
the fix: always acquiring locks in a deterministic order (e.g., sorting by primary key).
"""

import threading
import time
from decimal import Decimal

import psycopg
from app.dependencies import get_session_factory, init_db
from app.models import Account
from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import OperationalError


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


# Barrier to ensure threads cross-lock simultaneously
deadlock_barrier = threading.Barrier(2)


def bad_transfer_worker(worker_id: int, from_id: int, to_id: int, amount: Decimal) -> None:
    """A transfer function vulnerable to deadlocks because it doesn't sort the resources."""
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            with session.begin():
                logger.info(f"[Worker {worker_id}] Locking Account {from_id} (Source)...")
                acc_from = session.execute(select(Account).where(Account.id == from_id).with_for_update()).scalar_one()

                logger.info(f"[Worker {worker_id}] Locked Account {from_id}. Waiting for peer...")
                # Both threads must have acquired their first lock before proceeding
                deadlock_barrier.wait()

                logger.info(f"[Worker {worker_id}] Attempting to lock Account {to_id} (Destination)...")
                # This is where the deadlock occurs!
                acc_to = session.execute(select(Account).where(Account.id == to_id).with_for_update()).scalar_one()

                # Transfer logic
                acc_from.balance -= amount
                acc_to.balance += amount
                logger.success(f"[Worker {worker_id}] Transfer complete!")

    except OperationalError as e:
        if isinstance(e.orig, psycopg.errors.DeadlockDetected):
            logger.error(f"[Worker {worker_id}] 🔥 FATAL: psycopg.errors.DeadlockDetected! Transaction rolled back.")
        else:
            logger.error(f"[Worker {worker_id}] OperationalError: {e}")
    except Exception as e:
        logger.error(f"[Worker {worker_id}] Exception: {e}")


def good_transfer_worker(worker_id: int, from_id: int, to_id: int, amount: Decimal) -> None:
    """A safe transfer function that locks resources in deterministic order (by ID)."""
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            with session.begin():
                # DEDUPLICATE AND SORT
                lock_order = sorted([from_id, to_id])

                logger.info(f"[Worker {worker_id}] Locking Account {lock_order[0]} (First in order)...")
                acc_first = session.execute(
                    select(Account).where(Account.id == lock_order[0]).with_for_update()
                ).scalar_one()

                logger.info(f"[Worker {worker_id}] Locked Account {lock_order[0]}. Proceeding to second lock...")
                # We do NOT wait at a barrier here. If Thread 4 tries to lock Account 1,
                # it will be blocked by Postgres until Thread 3 finishes completely.

                logger.info(f"[Worker {worker_id}] Attempting to lock Account {lock_order[1]} (Second in order)...")
                acc_second = session.execute(
                    select(Account).where(Account.id == lock_order[1]).with_for_update()
                ).scalar_one()

                # Map back to from/to
                acc_from = acc_first if acc_first.id == from_id else acc_second
                acc_to = acc_second if acc_second.id == to_id else acc_first

                # Transfer logic
                acc_from.balance -= amount
                acc_to.balance += amount
                logger.success(f"[Worker {worker_id}] Transfer complete!")

    except Exception as e:
        logger.error(f"[Worker {worker_id}] Exception: {e}")


def main() -> None:
    """Main entry point for this lab step."""
    logger.info("Initializing database...")
    init_db()

    # --- TEST 1: THE DEADLOCK (Out of Order) ---
    print_separator("TEST 1: THE DEADLOCK (OUT OF ORDER)")
    logger.warning("Simulating a classic A->B and B->A concurrent transfer...")

    # Thread 1 transfers from 1 to 2. Thread 2 transfers from 2 to 1.
    t1 = threading.Thread(target=bad_transfer_worker, args=(1, 1, 2, Decimal("10.00")))
    t2 = threading.Thread(target=bad_transfer_worker, args=(2, 2, 1, Decimal("10.00")))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    logger.warning("Observation: Postgres detected the circular dependency and forcefully aborted one transaction.")

    # --- TEST 2: DETERMINISTIC ORDERING ---
    print_separator("TEST 2: DETERMINISTIC ORDERING FIX")
    logger.success("Simulating the same transfer, but both workers sort IDs and lock the lowest ID first.")

    deadlock_barrier.reset()

    t3 = threading.Thread(target=good_transfer_worker, args=(3, 1, 2, Decimal("10.00")))
    t4 = threading.Thread(target=good_transfer_worker, args=(4, 2, 1, Decimal("10.00")))

    t3.start()
    time.sleep(0.1)  # Stagger slightly to let t3 grab the first lock
    t4.start()

    t3.join()
    t4.join()

    logger.success("Observation: Worker 4 simply waited for Worker 3 to finish. No deadlocks!")

    logger.info("=" * 60)
    logger.info("Lab Step 2 Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
