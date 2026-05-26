"""
Lab Step 2: UUIDv4 vs. Sequential UUIDv7 (Index Fragmentation)

This script demonstrates:
- The performance and storage costs of UUIDv4 vs UUIDv7 primary keys under high write throughput.
- How random UUIDv4 primary keys cause severe B-Tree index page splitting (fragmentation).
- How time-ordered sequential UUIDv7 keys achieve O(1) append-only index growth.
- Benchmarking 100,000 insertions to compare insert latencies and final index sizes.
"""

import os
import time
import uuid

from app.dependencies import get_session_factory, init_db
from app.models import LogUUIDv4, LogUUIDv7
from loguru import logger
from sqlalchemy import text


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def generate_uuidv7() -> uuid.UUID:
    """
    Generate a time-ordered sequential UUIDv7 (RFC 4122) directly in Python.
    Ensures sequential sorting by prefixing with a 48-bit timestamp.
    """
    # Timestamp in milliseconds
    ms = int(time.time() * 1000)

    # Prefix: 48-bit timestamp bytes
    timestamp_bytes = ms.to_bytes(6, byteorder="big")

    # 10 bytes of entropy/randomness
    rand_bytes = os.urandom(10)

    # Combine bytes into a mutable array
    b = bytearray(timestamp_bytes + rand_bytes)

    # Set version bits to 7 (0111) in byte 6
    b[6] = (b[6] & 0x0F) | 0x70

    # Set variant bits to 2 (10) in byte 8
    b[8] = (b[8] & 0x3F) | 0x80

    return uuid.UUID(bytes=bytes(b))


def run_uuid_write_benchmarks(count: int = 100000) -> None:
    """Insert log records into both UUIDv4 and UUIDv7 tables and compare speeds."""
    print_separator(f"HIGH-THROUGHPUT INSERT BENCHMARK ({count:,} RECORDS)")

    session_factory = get_session_factory()
    batch_size = 10000

    # 1. Benchmark UUIDv4
    logger.info("[Benchmark 1] Starting UUIDv4 insertions...")
    start_v4 = time.time()

    with session_factory() as session:
        for i in range(0, count, batch_size):
            batch = []
            for j in range(batch_size):
                if i + j >= count:
                    break
                batch.append(
                    LogUUIDv4(
                        id=uuid.uuid4(),  # Random UUIDv4
                        message=f"Log entry UUIDv4 transaction index {i + j}",
                    )
                )
            session.add_all(batch)
            session.commit()
            if (i + batch_size) % 20000 == 0 or i + batch_size >= count:
                logger.info(f"  [v4 Progress] Inserted {min(i + batch_size, count):,} / {count:,} rows")

    elapsed_v4 = time.time() - start_v4
    logger.info(f"[Complete] Finished UUIDv4 inserts in {elapsed_v4:.2f}s ({count / elapsed_v4:.1f} writes/sec)")

    # 2. Benchmark UUIDv7
    logger.info("\n[Benchmark 2] Starting UUIDv7 insertions...")
    start_v7 = time.time()

    with session_factory() as session:
        for i in range(0, count, batch_size):
            batch = []
            for j in range(batch_size):
                if i + j >= count:
                    break
                batch.append(
                    LogUUIDv7(
                        id=generate_uuidv7(),  # Sequential time-ordered UUIDv7
                        message=f"Log entry UUIDv7 transaction index {i + j}",
                    )
                )
            session.add_all(batch)
            session.commit()
            if (i + batch_size) % 20000 == 0 or i + batch_size >= count:
                logger.info(f"  [v7 Progress] Inserted {min(i + batch_size, count):,} / {count:,} rows")

    elapsed_v7 = time.time() - start_v7
    logger.info(f"[Complete] Finished UUIDv7 inserts in {elapsed_v7:.2f}s ({count / elapsed_v7:.1f} writes/sec)")


def compare_index_sizes_and_fragmentation() -> None:
    """Examine final index sizing and statistics to demonstrate fragmentation."""
    print_separator("INDEX SIZE & FRAGMENTATION COMPARISON")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Run ANALYZE to update stats
        session.execute(text("ANALYZE logs_uuidv4"))
        session.execute(text("ANALYZE logs_uuidv7"))
        session.commit()

        # Query index sizes for primary keys
        result = session.execute(
            text("""
            SELECT
                'logs_uuidv4_pkey' as index_name,
                pg_size_pretty(pg_relation_size('logs_uuidv4_pkey')) as index_size,
                pg_relation_size('logs_uuidv4_pkey') as raw_bytes
            UNION ALL
            SELECT
                'logs_uuidv7_pkey' as index_name,
                pg_size_pretty(pg_relation_size('logs_uuidv7_pkey')) as index_size,
                pg_relation_size('logs_uuidv7_pkey') as raw_bytes
        """)
        )

        logger.info("[Primary Key Index Sizing]")
        rows = result.fetchall()
        for row in rows:
            logger.info(f"  Index: {row[0]:<20} Size: {row[1]}")

        # Calculate difference
        v4_bytes = rows[0][2]
        v7_bytes = rows[1][2]
        diff_percent = ((v4_bytes - v7_bytes) / v7_bytes) * 100.0

        logger.warning(
            f"\n[Index Fragmentation Alert] UUIDv4 primary key index is {diff_percent:.1f}% LARGER than UUIDv7!"
        )

        logger.info("==> [Why this happens]")
        logger.info("1. UUIDv4 is completely random. Insertions split existing B-Tree leaf pages (page splits).")
        logger.info("   This leaves leaf pages only 50-70% full, bloating the index size with empty space.")
        logger.info("2. UUIDv7 is time-ordered and sequential. Insertions always go to the rightmost leaf page.")
        logger.info("   This keeps page fill factors near 90-95%, maximizing storage and I/O efficiency.")
        logger.info(
            "3. For high-volume transaction/audit tables, sequential UUIDv7 prevents expensive random disk I/O!"
        )


def main() -> None:
    """Main entry point for Step 2."""
    logger.info("=" * 60)
    logger.info("LAB STEP 2: UUIDv4 vs. Sequential UUIDv7 (Index Fragmentation)")
    logger.info("=" * 60)

    logger.info("==> [Phase 1] Initializing database...")
    init_db()

    # Run benchmarks
    logger.info("==> [Phase 2] Simulating write benchmarks...")
    run_uuid_write_benchmarks(100000)

    # Compare statistics
    logger.info("==> [Phase 3] Analyzing B-Tree index fragmentation...")
    compare_index_sizes_and_fragmentation()

    logger.info("=" * 60)
    logger.info("Lab Step 2 Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
