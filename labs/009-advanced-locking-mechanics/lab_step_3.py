"""
Lab Step 3: Non-blocking Queues (NOWAIT & SKIP LOCKED)

This script demonstrates how to use PostgreSQL as a high-throughput, horizontally
scalable message queue by using the SKIP LOCKED modifier. This allows multiple
concurrent workers to grab batches of jobs without blocking each other.
"""

import threading
import time

from app.dependencies import get_session_factory, init_db
from app.models import Job
from loguru import logger
from sqlalchemy import select


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


# Used to start all workers at precisely the same time
start_barrier = threading.Barrier(3)


def blocking_worker(worker_id: int) -> None:
    """A naive worker that attempts to grab jobs using standard FOR UPDATE."""
    session_factory = get_session_factory()
    start_barrier.wait()

    with session_factory() as session:
        with session.begin():
            logger.info(f"[Worker {worker_id}] Searching for 2 pending jobs...")

            # This query will BLOCK if another worker has already locked the first rows
            stmt = select(Job).where(Job.status == "pending").limit(2).with_for_update()
            jobs = session.scalars(stmt).all()

            if not jobs:
                logger.warning(f"[Worker {worker_id}] No pending jobs found.")
                return

            job_ids = [j.id for j in jobs]
            logger.error(f"[Worker {worker_id}] Acquired lock on Jobs: {job_ids} (Notice the serial execution time!)")

            # Simulate work
            time.sleep(1.0)

            for job in jobs:
                job.status = "completed"

            logger.success(f"[Worker {worker_id}] Completed Jobs: {job_ids}")


def skip_locked_worker(worker_id: int) -> None:
    """A highly scalable worker that uses SKIP LOCKED to process jobs concurrently."""
    session_factory = get_session_factory()
    start_barrier.wait()

    with session_factory() as session:
        with session.begin():
            logger.info(f"[Worker {worker_id}] Searching for 2 pending jobs with SKIP LOCKED...")

            # This query skips any rows locked by other transactions instantly!
            stmt = select(Job).where(Job.status == "pending").limit(2).with_for_update(skip_locked=True)
            jobs = session.scalars(stmt).all()

            if not jobs:
                logger.warning(f"[Worker {worker_id}] No pending jobs found (all were locked or completed).")
                return

            job_ids = [j.id for j in jobs]
            logger.success(f"[Worker {worker_id}] Instantly acquired lock on Jobs: {job_ids}")

            # Simulate work
            time.sleep(1.0)

            for job in jobs:
                job.status = "completed"

            logger.success(f"[Worker {worker_id}] Completed Jobs: {job_ids}")


def main() -> None:
    """Main entry point for this lab step."""
    logger.info("Initializing database...")
    init_db()

    # --- TEST 1: STANDARD FOR UPDATE (BLOCKING QUEUE) ---
    print_separator("TEST 1: BLOCKING QUEUE (STANDARD FOR UPDATE)")
    logger.warning("Spawning 3 workers. They will all try to grab the first 'pending' jobs.")
    logger.warning("Because they do not use SKIP LOCKED, they will block each other serially.")

    start_time = time.time()

    threads = []
    for i in range(1, 4):
        t = threading.Thread(target=blocking_worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    elapsed = time.time() - start_time
    logger.error(f"Test 1 completed in {elapsed:.2f} seconds. (Workers waited for each other)")

    # Reset the database to provide fresh pending jobs
    init_db()

    # --- TEST 2: SKIP LOCKED (CONCURRENT QUEUE) ---
    print_separator("TEST 2: CONCURRENT QUEUE (SKIP LOCKED)")
    logger.success("Spawning 3 workers using SKIP LOCKED.")
    logger.success("Worker 1 grabs jobs 1-2. Worker 2 skips them and grabs 3-4 instantly!")

    start_barrier.reset()
    start_time = time.time()

    threads = []
    for i in range(4, 7):
        t = threading.Thread(target=skip_locked_worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    elapsed = time.time() - start_time
    logger.success(f"Test 2 completed in {elapsed:.2f} seconds. (Workers processed simultaneously!)")

    logger.info("=" * 60)
    logger.info("Lab Step 3 Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
