from app.dependencies import get_db_engine, get_session_factory, init_db
from app.models import DiagnosticItem
from loguru import logger
from sqlalchemy import text


def get_cache_statistics(conn):
    """Query pg_statio_user_tables to get hit vs read metrics."""
    sql = text(
        """
        SELECT
            sum(heap_blks_read) as blks_read,
            sum(heap_blks_hit) as blks_hit
        FROM pg_statio_all_tables
        WHERE schemaname = 'public';
        """
    )
    res = conn.execute(sql).fetchone()
    if res and res[0] is not None and res[1] is not None:
        read = res[0]
        hit = res[1]
        total = read + hit
        ratio = (hit / total * 100) if total > 0 else 100.0
        return read, hit, ratio
    return 0, 0, 100.0


def main():
    logger.info("Initializing database...")
    init_db()

    session_factory = get_session_factory()
    logger.info("Seeding table with 50,000 records to create disk footprint...")
    with session_factory() as session:
        # Batch insert
        items = [DiagnosticItem(name=f"item_{i}", value=float(i)) for i in range(50000)]
        session.add_all(items)
        session.commit()

    engine = get_db_engine()

    # 1. Warm cache query
    logger.info("Querying database to populate shared_buffers cache...")
    with engine.connect() as conn:
        conn.execute(text("SELECT SUM(value) FROM diagnostic_items"))

    # Measure cache hit ratio
    logger.info("Measuring buffer cache hit ratio on warmed query...")
    with engine.connect() as conn:
        read, hit, ratio = get_cache_statistics(conn)
        logger.info("Public Tables Cache Stats:")
        logger.info(f"  * Blocks Read from Disk: {read}")
        logger.info(f"  * Blocks Hit in Cache: {hit}")
        logger.info(f"  * Cache Hit Ratio: {ratio:.2f}%")

    # 2. Simulate Disk Queue Depth calculations
    print("=" * 20 + " CLOUDWATCH METRIC SIMULATION " + "=" * 20)
    logger.info("Calculating CPU & Disk Metrics using Little's Law:")
    logger.info("Little's Law: Disk Queue Depth = IOPS * Latency (seconds)")

    # Scenario A: Fast storage (GP3 with high IOPS, 1ms latency)
    iops = 3000  # 3000 read operations per second
    latency_fast = 0.001  # 1ms latency
    q_depth_fast = iops * latency_fast

    # Scenario B: Slow/throttled storage (Burst credits exhausted, 15ms latency)
    latency_slow = 0.015  # 15ms latency
    q_depth_slow = iops * latency_slow

    logger.info("Scenario A (Healthy GP3 Storage - 1ms Latency):")
    logger.info(f"  * Throughput: {iops} IOPS")
    logger.info(f"  * Latency: {latency_fast * 1000:.1f} ms")
    logger.info(f"  * Calculated CloudWatch DiskQueueDepth: {q_depth_fast:.2f}")

    logger.info("Scenario B (Throttled GP2 Storage - 15ms Latency):")
    logger.info(f"  * Throughput: {iops} IOPS")
    logger.info(f"  * Latency: {latency_slow * 1000:.1f} ms")
    logger.info(f"  * Calculated CloudWatch DiskQueueDepth: {q_depth_slow:.2f} (Danger Zone!)")

    logger.info("Key Production Takeaways:")
    logger.info(
        "1. FreeableMemory: Ensure this is high. If it drops to near 0, the OS cannot cache disk blocks, forcing PostgreSQL to perform expensive physical disk reads."
    )
    logger.info(
        "2. DiskQueueDepth: A sustained queue depth higher than 1 (per 1000 provisioned IOPS) indicates that storage cannot keep up with database request volume."
    )
    logger.info(
        "3. Read/Write Latency: If latency spikes above 5-10ms, database queries will stall, causing Average Active Sessions (AAS) to balloon, triggering API timeouts in FastAPI."
    )

    logger.info("=" * 60)
    logger.info("Lab Step 3 Complete!")


if __name__ == "__main__":
    main()
