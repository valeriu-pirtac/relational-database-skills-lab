"""
Lab Step 0: Standard Data Types Overview & Rounding Pitfalls

This script demonstrates:
- PostgreSQL standard data types (Integers, Characters, Floats, Decimals, Booleans)
- The critical production pitfall of Floating-Point Rounding Errors
- Why NUMERIC is mandatory for monetary values in production
"""

import time
from decimal import Decimal

from app.dependencies import get_session_factory, init_db
from app.models import StandardTypesDemo
from loguru import logger
from sqlalchemy import text


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def demonstrate_standard_types() -> None:
    """Create a sample record and inspect table storage sizes."""
    print_separator("DEMONSTRATING STANDARD TYPES")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Create a sample record using diverse types
        logger.info("[Action] Inserting a standard types demo record...")
        demo = StandardTypesDemo(
            small_int=32767,  # Max for smallint (2 bytes)
            big_int=2147483647,  # Max for integer (4 bytes)
            float_val=12345.6789,  # Double precision float (8 bytes)
            numeric_val=Decimal("12345.67"),  # Exact decimal numeric (10, 2)
            char_fixed="Postgres",  # Padded to 10 chars under the hood
            varchar_var="SQLAlchemy is extremely powerful",  # Variable length
            text_val="Lorem ipsum dolor sit amet, consectetur adipiscing elit." * 10,  # Unlimited
        )
        session.add(demo)
        session.commit()

        # Query catalog to check table details
        logger.info("[Catalog] Querying schema attributes and table statistics...")
        result = session.execute(
            text("""
            SELECT
                pg_size_pretty(pg_relation_size('standard_types_demo')) as table_size,
                (SELECT count(*) FROM standard_types_demo) as row_count
        """)
        )
        row = result.fetchone()
        logger.info(f"[Table Stats] Size: {row[0]}, Row Count: {row[1]}")


def demonstrate_rounding_pitfall() -> None:
    """Demonstrate how double precision float rounding drifts under bulk operations."""
    print_separator("THE FLOATING-POINT ROUNDING PITFALL")

    session_factory = get_session_factory()
    count = 10000
    increment_str = "0.1"
    increment_float = 0.1
    increment_decimal = Decimal(increment_str)

    logger.info(f"[Simulation] Simulating {count:,} micro-transactions of {increment_str} cents...")
    logger.info("Comparing DOUBLE PRECISION (Inexact Float) vs. NUMERIC (Exact Decimal)...")

    # Insert transactions in a bulk insert
    with session_factory() as session:
        # We will insert records using raw SQL for speed in this simulation
        start_time = time.time()

        # Batch insert to avoid SQL overhead
        session.execute(
            text("""
            INSERT INTO standard_types_demo (float_val, numeric_val)
            SELECT :f_val, :n_val
            FROM generate_series(1, :count)
        """),
            {"f_val": increment_float, "n_val": increment_decimal, "count": count},
        )
        session.commit()

        elapsed = time.time() - start_time
        logger.info(f"[Complete] Inserted {count:,} test records in {elapsed:.2f}s")

    # Sum them up and see the difference!
    with session_factory() as session:
        result = session.execute(
            text("""
            SELECT
                SUM(float_val) as inexact_float_sum,
                SUM(numeric_val) as exact_numeric_sum
            FROM standard_types_demo
            WHERE float_val IS NOT NULL
        """)
        )
        float_sum, numeric_sum = result.fetchone()

        # Calculate mathematically expected sum: 10000 * 0.1 = 1000.0
        expected_sum = count * increment_float

        logger.info("-" * 50)
        logger.info(f"  Expected Sum:   {expected_sum:.2f}")
        logger.info(f"  Exact NUMERIC:  {numeric_sum}")
        logger.info(f"  Float SUM:      {float_sum}")
        logger.info("-" * 50)

        # Highlight the discrepancy
        drift = float(numeric_sum) - float_sum
        logger.warning(f"  [Drift Detected] Inexact Float drift from expected sum: {drift:+0.16f}")

        logger.info("==> [Key Insight] Binary floats cannot represent decimal fractions like 0.1 precisely.")
        logger.info(
            "Over millions of records, float rounding errors accumulate into significant financial discrepancies."
        )
        logger.info("==> [Key Insight] Always use NUMERIC/DECIMAL types for monetary or exact transactional math!")


def main() -> None:
    """Main entry point for Step 0."""
    logger.info("=" * 60)
    logger.info("LAB STEP 0: Standard Data Types Overview & Rounding Pitfalls")
    logger.info("=" * 60)

    logger.info("==> [Phase 1] Initializing database...")
    init_db()

    # Execute step routines
    logger.info("==> [Phase 2] Examining standard types...")
    demonstrate_standard_types()

    logger.info("==> [Phase 3] Demonstrating floating-point rounding errors...")
    demonstrate_rounding_pitfall()

    logger.info("=" * 60)
    logger.info("Lab Step 0 Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
