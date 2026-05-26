"""
Lab Step 3: BRIN Indexes for Timeseries Data

This script demonstrates:
- BRIN (Block Range Index) for massive, naturally ordered datasets
- Dramatic space savings compared to B-Tree indexes
- Performance characteristics for range queries on timeseries data
- When to use BRIN vs B-Tree vs no index
"""

import time
from datetime import datetime, timedelta

from app.dependencies import get_session_factory, init_db
from app.models import SensorReading
from faker import Faker
from loguru import logger
from sqlalchemy import text


fake = Faker()
Faker.seed(456)


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def generate_sensor_data(count: int = 500000) -> None:
    """
    Generate timeseries sensor data with natural time ordering.
    This mimics real IoT sensor data being inserted chronologically.
    """
    print_separator(f"GENERATING {count:,} SENSOR READINGS")

    session_factory = get_session_factory()
    batch_size = 10000

    sensors = [f"SENSOR_{i:03d}" for i in range(1, 21)]  # 20 sensors
    locations = ["Building_A", "Building_B", "Building_C", "Building_D"]

    # Start from 90 days ago
    base_time = datetime.utcnow() - timedelta(days=90)

    with session_factory() as session:
        for i in range(0, count, batch_size):
            readings = []
            for j in range(batch_size):
                if i + j >= count:
                    break

                # Each reading is roughly 15 seconds after the previous
                # This creates naturally ordered data
                current_time = base_time + timedelta(seconds=(i + j) * 15)

                reading = SensorReading(
                    sensor_id=fake.random.choice(sensors),
                    temperature=fake.random.randint(1500, 3500),  # 15.00°C to 35.00°C
                    humidity=fake.random.randint(3000, 8000),  # 30.00% to 80.00%
                    pressure=fake.random.randint(98000, 104000),  # Atmospheric pressure
                    location=fake.random.choice(locations),
                    recorded_at=current_time,
                )
                readings.append(reading)

            session.add_all(readings)
            session.commit()
            logger.info(f"[Progress] Inserted {min(i + batch_size, count):,} / {count:,} readings")

    # Run ANALYZE to update statistics
    with session_factory() as session:
        session.execute(text("ANALYZE sensor_readings"))
        session.commit()

    logger.info(f"[Complete] Generated {count:,} sensor readings")


def show_table_size() -> None:
    """Display table size information."""
    print_separator("TABLE SIZE STATISTICS")

    session_factory = get_session_factory()

    with session_factory() as session:
        result = session.execute(
            text("""
            SELECT
                pg_size_pretty(pg_total_relation_size('sensor_readings')) as total_size,
                pg_size_pretty(pg_relation_size('sensor_readings')) as table_size,
                (SELECT COUNT(*) FROM sensor_readings) as row_count
        """)
        )
        row = result.fetchone()
        logger.info(f"[Table Size] Total: {row[0]}, Data: {row[1]}, Rows: {row[2]:,}")


def test_range_query_without_index() -> None:
    """Test time range query without any index on recorded_at."""
    print_separator("BASELINE: Time Range Query (No Index)")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Drop the auto-created SQLAlchemy index if it exists
        session.execute(text("DROP INDEX IF EXISTS ix_sensor_readings_recorded_at"))
        session.commit()

        # Test 7-day range query
        logger.info("\n[Query] Fetching last 7 days of data")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT sensor_id, temperature, humidity, recorded_at
            FROM sensor_readings
            WHERE recorded_at >= NOW() - INTERVAL '7 days'
            ORDER BY recorded_at DESC
            LIMIT 1000
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")


def create_btree_index() -> None:
    """Create standard B-Tree index on recorded_at for comparison."""
    print_separator("CREATING B-TREE INDEX")

    session_factory = get_session_factory()

    with session_factory() as session:
        start_time = time.time()

        session.execute(
            text("""
            CREATE INDEX idx_sensor_readings_recorded_at_btree
            ON sensor_readings (recorded_at)
        """)
        )
        session.commit()

        # Run ANALYZE to update statistics after index creation
        session.execute(text("ANALYZE sensor_readings"))
        session.commit()

        elapsed = time.time() - start_time
        logger.info(f"[Created] B-Tree index in {elapsed:.2f}s")

        # Show index size
        result = session.execute(
            text("""
            SELECT pg_size_pretty(pg_relation_size('idx_sensor_readings_recorded_at_btree'))
        """)
        )
        size = result.fetchone()[0]
        logger.info(f"[Index Size] {size}")


def test_range_query_with_btree() -> None:
    """Test time range query with B-Tree index."""
    print_separator("WITH B-TREE INDEX: Time Range Query")

    session_factory = get_session_factory()

    with session_factory() as session:
        logger.info("[Query] Fetching last 7 days of data")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT sensor_id, temperature, humidity, recorded_at
            FROM sensor_readings
            WHERE recorded_at >= NOW() - INTERVAL '7 days'
            ORDER BY recorded_at DESC
            LIMIT 1000
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")


def create_brin_index() -> None:
    """Create BRIN index on recorded_at."""
    print_separator("CREATING BRIN INDEX")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Drop B-Tree index first
        session.execute(text("DROP INDEX IF EXISTS idx_sensor_readings_recorded_at_btree"))
        session.commit()
        logger.info("[Cleanup] Dropped B-Tree index")

        start_time = time.time()

        # Create BRIN index with default pages_per_range (128 pages)
        session.execute(
            text("""
            CREATE INDEX idx_sensor_readings_recorded_at_brin
            ON sensor_readings USING BRIN (recorded_at)
        """)
        )
        session.commit()

        # Run ANALYZE to update statistics after index creation
        session.execute(text("ANALYZE sensor_readings"))
        session.commit()

        elapsed = time.time() - start_time
        logger.info(f"[Created] BRIN index in {elapsed:.2f}s")

        # Show index size
        result = session.execute(
            text("""
            SELECT pg_size_pretty(pg_relation_size('idx_sensor_readings_recorded_at_brin'))
        """)
        )
        size = result.fetchone()[0]
        logger.info(f"[Index Size] {size}")


def test_range_query_with_brin() -> None:
    """Test time range query with BRIN index."""
    print_separator("WITH BRIN INDEX: Time Range Query")

    session_factory = get_session_factory()

    with session_factory() as session:
        logger.info("[Query 1] Fetching last 7 days of data")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT sensor_id, temperature, humidity, recorded_at
            FROM sensor_readings
            WHERE recorded_at >= NOW() - INTERVAL '7 days'
            ORDER BY recorded_at DESC
            LIMIT 1000
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")

        logger.info("\n[Query 2] Aggregate query over last 24 hours")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT
                sensor_id,
                AVG(temperature / 100.0) as avg_temp,
                AVG(humidity / 100.0) as avg_humidity,
                COUNT(*) as reading_count
            FROM sensor_readings
            WHERE recorded_at >= NOW() - INTERVAL '1 day'
            GROUP BY sensor_id
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")


def compare_index_sizes() -> None:
    """Create both indexes temporarily to compare sizes."""
    print_separator("INDEX SIZE COMPARISON")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Create B-Tree index
        logger.info("[Creating] B-Tree index for comparison...")
        session.execute(
            text("""
            CREATE INDEX idx_sensor_readings_recorded_at_btree
            ON sensor_readings (recorded_at)
        """)
        )
        session.commit()

        # Get sizes
        result = session.execute(
            text("""
            SELECT
                'Table Data' as object,
                pg_size_pretty(pg_relation_size('sensor_readings')) as size,
                100.0 as percent
            UNION ALL
            SELECT
                'B-Tree Index' as object,
                pg_size_pretty(pg_relation_size('idx_sensor_readings_recorded_at_btree')) as size,
                ROUND((100.0 * pg_relation_size('idx_sensor_readings_recorded_at_btree')::float /
                      pg_relation_size('sensor_readings'))::numeric, 2) as percent
            UNION ALL
            SELECT
                'BRIN Index' as object,
                pg_size_pretty(pg_relation_size('idx_sensor_readings_recorded_at_brin')) as size,
                ROUND((100.0 * pg_relation_size('idx_sensor_readings_recorded_at_brin')::float /
                      pg_relation_size('sensor_readings'))::numeric, 2) as percent
        """)
        )

        logger.info("[Size Comparison]")
        for row in result:
            logger.info(f"  {row[0]}: {row[1]} ({row[2]:.2f}% of table)")

        # Calculate space savings
        result = session.execute(
            text("""
            SELECT
                pg_relation_size('idx_sensor_readings_recorded_at_btree') as btree_size,
                pg_relation_size('idx_sensor_readings_recorded_at_brin') as brin_size
        """)
        )
        row = result.fetchone()
        savings = 100.0 * (1 - row[1] / row[0])
        logger.info(f"\n[Savings] BRIN is {savings:.1f}% smaller than B-Tree")

        # Drop B-Tree index (keep BRIN)
        session.execute(text("DROP INDEX idx_sensor_readings_recorded_at_btree"))
        session.commit()


def demonstrate_brin_limitations() -> None:
    """Show scenarios where BRIN performs poorly."""
    print_separator("BRIN LIMITATIONS")

    session_factory = get_session_factory()

    with session_factory() as session:
        logger.info("[Limitation 1] Point lookup by specific timestamp")
        logger.info("BRIN is NOT efficient for exact value lookups")

        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT *
            FROM sensor_readings
            WHERE recorded_at = '2026-03-15 12:00:00'
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")

        logger.info("\n[Note] For point lookups, B-Tree would be much faster")
        logger.info("BRIN excels at range scans on large, naturally ordered data")


def main() -> None:
    """Main entry point for Lab Step 3."""
    logger.info("=" * 60)
    logger.info("LAB STEP 3: BRIN Indexes for Timeseries Data")
    logger.info("=" * 60)

    logger.info("==> [Phase 0] Initializing database...")
    init_db()

    # Generate sensor data
    logger.info("==> [Phase 1] Generating timeseries sensor data...")
    generate_sensor_data(500000)

    # Show table size
    show_table_size()

    # Test without index
    logger.info("==> [Phase 2] Testing range query without index...")
    test_range_query_without_index()

    # Create and test B-Tree
    logger.info("==> [Phase 3] Creating B-Tree index...")
    create_btree_index()

    logger.info("==> [Phase 4] Testing range query with B-Tree...")
    test_range_query_with_btree()

    # Create and test BRIN
    logger.info("==> [Phase 5] Creating BRIN index...")
    create_brin_index()

    logger.info("==> [Phase 6] Testing range query with BRIN...")
    test_range_query_with_brin()

    # Compare sizes
    logger.info("==> [Phase 7] Comparing index sizes...")
    compare_index_sizes()

    # Show limitations
    logger.info("==> [Phase 8] Demonstrating BRIN limitations...")
    demonstrate_brin_limitations()

    logger.info("=" * 60)
    logger.info("Lab Step 3 Complete!")
    logger.info("=" * 60)
    logger.info("==> [Key Insight] BRIN indexes provide massive space savings for")
    logger.info("naturally ordered data like timeseries, with acceptable performance")
    logger.info("for range queries. They are NOT suitable for random lookups.")


if __name__ == "__main__":
    main()
