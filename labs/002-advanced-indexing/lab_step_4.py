"""
Lab Step 4: Expression Indexes and Performance Comparison

This script demonstrates:
- Expression indexes for case-insensitive searches
- Composite expression indexes
- When expression indexes are beneficial
- Complete performance comparison of all index types
"""

import time

from app.dependencies import get_session_factory, init_db
from app.models import User
from faker import Faker
from loguru import logger
from sqlalchemy import text


fake = Faker()
Faker.seed(789)


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def generate_sample_users(count: int = 100000) -> None:
    """Generate sample user data."""
    print_separator(f"GENERATING {count:,} SAMPLE USERS")

    session_factory = get_session_factory()
    batch_size = 10000

    with session_factory() as session:
        for i in range(0, count, batch_size):
            users = []
            for j in range(batch_size):
                if i + j >= count:
                    break

                user = User(
                    email=f"{fake.user_name()}_{i + j}@{fake.free_email_domain()}",
                    username=fake.user_name(),
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    active=fake.random.random() < 0.9,
                )
                users.append(user)

            session.add_all(users)
            session.commit()
            logger.info(f"[Progress] Inserted {min(i + batch_size, count):,} / {count:,} users")

    # Run ANALYZE to update statistics
    with session_factory() as session:
        session.execute(text("ANALYZE users"))
        session.commit()

    logger.info(f"[Complete] Generated {count:,} users")


def test_case_insensitive_search_without_index() -> None:
    """Test case-insensitive email search without expression index."""
    print_separator("BASELINE: Case-Insensitive Email Search (No Expression Index)")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Get a sample email to search for
        result = session.execute(text("SELECT email FROM users LIMIT 1"))
        sample_email = result.fetchone()[0].lower()

        logger.info(f"[Query] Searching for email: {sample_email}")
        result = session.execute(
            text(f"""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, username, email
            FROM users
            WHERE LOWER(email) = '{sample_email}'
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")


def create_expression_index_on_email() -> None:
    """Create expression index for case-insensitive email searches."""
    print_separator("CREATING EXPRESSION INDEX ON LOWER(email)")

    session_factory = get_session_factory()

    with session_factory() as session:
        start_time = time.time()

        session.execute(
            text("""
            CREATE INDEX idx_users_email_lower
            ON users (LOWER(email))
        """)
        )
        session.commit()

        # Run ANALYZE to update statistics after index creation
        session.execute(text("ANALYZE users"))
        session.commit()

        elapsed = time.time() - start_time
        logger.info(f"[Created] Expression index in {elapsed:.2f}s")

        # Show index size
        result = session.execute(
            text("""
            SELECT pg_size_pretty(pg_relation_size('idx_users_email_lower'))
        """)
        )
        size = result.fetchone()[0]
        logger.info(f"[Index Size] {size}")


def test_case_insensitive_search_with_index() -> None:
    """Test case-insensitive email search with expression index."""
    print_separator("WITH EXPRESSION INDEX: Case-Insensitive Email Search")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Get a sample email
        result = session.execute(text("SELECT email FROM users LIMIT 1"))
        sample_email = result.fetchone()[0].lower()

        logger.info(f"[Query] Searching for email: {sample_email}")
        result = session.execute(
            text(f"""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, username, email
            FROM users
            WHERE LOWER(email) = '{sample_email}'
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")


def create_composite_expression_index() -> None:
    """Create composite expression index for full name searches."""
    print_separator("CREATING COMPOSITE EXPRESSION INDEX")

    session_factory = get_session_factory()

    with session_factory() as session:
        start_time = time.time()

        # Create index on concatenated full name (case-insensitive)
        session.execute(
            text("""
            CREATE INDEX idx_users_full_name_lower
            ON users (LOWER(first_name || ' ' || last_name))
        """)
        )
        session.commit()

        # Run ANALYZE to update statistics after index creation
        session.execute(text("ANALYZE users"))
        session.commit()

        elapsed = time.time() - start_time
        logger.info(f"[Created] Composite expression index in {elapsed:.2f}s")

        # Show index size
        result = session.execute(
            text("""
            SELECT pg_size_pretty(pg_relation_size('idx_users_full_name_lower'))
        """)
        )
        size = result.fetchone()[0]
        logger.info(f"[Index Size] {size}")


def test_full_name_search() -> None:
    """Test full name search using the composite expression index."""
    print_separator("TESTING COMPOSITE EXPRESSION INDEX")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Get a sample name
        result = session.execute(text("SELECT first_name, last_name FROM users LIMIT 1"))
        first, last = result.fetchone()
        full_name = f"{first} {last}".lower()

        logger.info(f"[Query 1] Exact match for: {full_name}")
        result = session.execute(
            text(f"""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, email, first_name, last_name
            FROM users
            WHERE LOWER(first_name || ' ' || last_name) = '{full_name}'
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")

        # Test LIKE query
        logger.info(f"[Query 2] LIKE search for '%{last.lower()}%'")
        result = session.execute(
            text(f"""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, email, first_name, last_name
            FROM users
            WHERE LOWER(first_name || ' ' || last_name) LIKE '%{last.lower()}%'
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")

        logger.info("[Note] Expression indexes help with exact matches and prefix searches,")
        logger.info("but not with LIKE patterns that start with '%'")


def compare_all_index_types() -> None:
    """Summary comparison of all index types covered in the lab."""
    print_separator("COMPREHENSIVE INDEX TYPE COMPARISON")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Get statistics for all indexes
        result = session.execute(
            text("""
            SELECT
                i.relname,
                i.indexrelname,
                am.amname AS index_type,
                pg_size_pretty(pg_relation_size(i.indexrelid)) AS index_size,
                i.idx_scan AS scans,
                pg_size_pretty(pg_relation_size(i.relname::regclass)) AS table_size
            FROM
                pg_stat_user_indexes i
                JOIN pg_class c ON c.oid = i.indexrelid
                JOIN pg_am am ON am.oid = c.relam
            WHERE
                i.schemaname = 'public'
            ORDER BY
                pg_relation_size(i.indexrelid) DESC
        """)
        )

        logger.info("[All Indexes in Database]")
        logger.info(f"{'Table':<20} {'Index Name':<40} {'Type':<8} {'Size':<12} {'Scans':<10}")
        logger.info("-" * 100)

        for row in result:
            logger.info(f"{row[0]:<20} {row[1]:<40} {row[2]:<8} {row[3]:<12} {row[4]:<10}")


def show_index_usage_summary() -> None:
    """Display summary of when to use each index type."""
    print_separator("INDEX SELECTION GUIDE")

    logger.info("[B-Tree Index (Default)]")
    logger.info("  Use for: General purpose, equality and range queries")
    logger.info("  Size: Medium to Large (grows with data)")
    logger.info("  Performance: Excellent for point lookups and ranges")
    logger.info("  Best for: Most use cases, unique constraints")

    logger.info("[Partial Index]")
    logger.info("  Use for: Queries that filter on specific conditions")
    logger.info("  Size: Smaller than full index (only indexes subset)")
    logger.info("  Performance: Same as B-Tree for matching queries")
    logger.info("  Best for: active=true, status='published', etc.")

    logger.info("[GIN Index (Generalized Inverted)]")
    logger.info("  Use for: JSONB, arrays, full-text search")
    logger.info("  Size: Large (inverted index structure)")
    logger.info("  Performance: Excellent for containment queries (@>, ?, @@)")
    logger.info("  Best for: JSONB metadata, tags, search vectors")

    logger.info("[BRIN Index (Block Range)]")
    logger.info("  Use for: Massive tables with natural ordering")
    logger.info("  Size: Tiny (0.1% - 1% of B-Tree)")
    logger.info("  Performance: Good for ranges, poor for point lookups")
    logger.info("  Best for: Timeseries data, logs, append-only tables")

    logger.info("[Expression Index]")
    logger.info("  Use for: Queries on computed values or functions")
    logger.info("  Size: Same as B-Tree on the expression")
    logger.info("  Performance: Excellent when query matches expression")
    logger.info("  Best for: LOWER(email), date_trunc(), computed columns")


def show_production_recommendations() -> None:
    """Production-level recommendations and anti-patterns."""
    print_separator("PRODUCTION RECOMMENDATIONS")

    logger.info("[DO]")
    logger.info("  ✓ Create indexes CONCURRENTLY in production")
    logger.info("  ✓ Monitor index usage with pg_stat_user_indexes")
    logger.info("  ✓ Drop unused indexes (idx_scan = 0)")
    logger.info("  ✓ Use partial indexes for large tables with filters")
    logger.info("  ✓ Consider BRIN for massive timeseries tables (> 10M rows)")
    logger.info("  ✓ Use GIN for JSONB queries with @> operator")
    logger.info("  ✓ Test index impact with EXPLAIN (ANALYZE, BUFFERS)")

    logger.info("[DON'T]")
    logger.info("  ✗ Create indexes without measuring query performance")
    logger.info("  ✗ Index every column 'just in case'")
    logger.info("  ✗ Use BRIN for randomly accessed data")
    logger.info("  ✗ Forget to update statistics (ANALYZE) after bulk loads")
    logger.info("  ✗ Create duplicate indexes (e.g., on same columns)")
    logger.info("  ✗ Use expression indexes if the expression can't be matched")

    logger.info("[Production Gotchas]")
    logger.info("  ⚠ CREATE INDEX locks the table (use CONCURRENTLY)")
    logger.info("  ⚠ GIN indexes have higher write cost than B-Tree")
    logger.info("  ⚠ BRIN requires VACUUM to maintain efficiency")
    logger.info("  ⚠ Too many indexes slow down INSERT/UPDATE/DELETE")
    logger.info("  ⚠ Expression indexes only work if query matches expression exactly")


def main() -> None:
    """Main entry point for Lab Step 4."""
    logger.info("=" * 60)
    logger.info("LAB STEP 4: Expression Indexes and Performance Comparison")
    logger.info("=" * 60)

    logger.info("==> [Phase 0] Initializing database...")
    init_db()

    # Generate user data
    logger.info("==>[Phase 1] Generating user data...")
    generate_sample_users(100000)

    # Test case-insensitive search without index
    logger.info("==>[Phase 2] Testing case-insensitive search without index...")
    test_case_insensitive_search_without_index()

    # Create expression index on email
    logger.info("==>[Phase 3] Creating expression index on LOWER(email)...")
    create_expression_index_on_email()

    # Test with expression index
    logger.info("==>[Phase 4] Testing case-insensitive search with index...")
    test_case_insensitive_search_with_index()

    # Create composite expression index
    logger.info("==>[Phase 5] Creating composite expression index...")
    create_composite_expression_index()

    # Test full name search
    logger.info("==>[Phase 6] Testing full name search...")
    test_full_name_search()

    # Compare all index types
    logger.info("==>[Phase 7] Comparing all index types...")
    compare_all_index_types()

    # Show usage summary
    logger.info("==>[Phase 8] Index selection guide...")
    show_index_usage_summary()

    # Show production recommendations
    logger.info("==>[Phase 9] Production recommendations...")
    show_production_recommendations()

    logger.info("=" * 60)
    logger.info("Lab Step 4 Complete!")
    logger.info("=" * 60)
    logger.info("==>[Key Insight] Expression indexes enable efficient queries on")
    logger.info("computed values, but must match the exact expression in your query.")


if __name__ == "__main__":
    main()
