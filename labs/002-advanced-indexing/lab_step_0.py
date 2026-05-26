"""
Lab Step 0: B-Tree Index Fundamentals

This script demonstrates:
- PostgreSQL's default B-Tree index structure
- Index scan vs Sequential scan
- When PostgreSQL chooses to use an index
- Basic EXPLAIN ANALYZE interpretation
- Setting up baseline data for subsequent labs
"""

import time

from app.dependencies import get_session_factory, init_db
from app.models import Product
from faker import Faker
from loguru import logger
from sqlalchemy import text


fake = Faker()
Faker.seed(42)


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"\n{'=' * 20} {title} {'=' * 20}")


def generate_sample_products(count: int = 50000) -> None:
    """
    Generate sample product data with realistic distribution:
    - 70% active products
    - 30% inactive products
    """
    print_separator(f"GENERATING {count:,} SAMPLE PRODUCTS")

    session_factory = get_session_factory()
    batch_size = 5000

    categories = ["Electronics", "Clothing", "Home & Garden", "Books", "Sports", "Toys"]

    with session_factory() as session:
        for i in range(0, count, batch_size):
            products = []
            for j in range(batch_size):
                if i + j >= count:
                    break

                # 70% active, 30% inactive
                is_active = fake.random.random() < 0.7

                product = Product(
                    name=fake.catch_phrase(),
                    category=fake.random.choice(categories),
                    description=fake.text(max_nb_chars=200),
                    price=fake.random.randint(500, 50000),  # $5 to $500
                    active=is_active,
                    attributes={
                        "brand": fake.company(),
                        "weight_kg": round(fake.random.uniform(0.1, 50.0), 2),
                        "dimensions": {
                            "length": fake.random.randint(10, 200),
                            "width": fake.random.randint(10, 200),
                            "height": fake.random.randint(10, 200),
                        },
                        "features": fake.random.choices(
                            [
                                "wireless",
                                "bluetooth",
                                "waterproof",
                                "rechargeable",
                                "portable",
                            ],
                            k=fake.random.randint(1, 3),
                        ),
                        "color": fake.random.choice(["red", "blue", "black", "white", "silver"]),
                    },
                )
                products.append(product)

            session.add_all(products)
            session.commit()
            logger.info(f"[Progress] Inserted {min(i + batch_size, count):,} / {count:,} products")

    logger.info(f"[Complete] Generated {count:,} products")


def show_table_stats() -> None:
    """Display table statistics."""
    print_separator("TABLE STATISTICS")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Table size
        result = session.execute(
            text("""
            SELECT
                pg_size_pretty(pg_total_relation_size('products')) as total_size,
                pg_size_pretty(pg_relation_size('products')) as table_size
        """)
        )
        row = result.fetchone()
        logger.info(f"[Table Size] Total: {row[0]}, Data: {row[1]}")

        # Row counts
        total = session.query(Product).count()
        logger.info(f"[Row Count] {total:,} products")


def test_sequential_scan() -> None:
    """Demonstrate sequential scan behavior without indexes."""
    print_separator("SEQUENTIAL SCAN: No Indexes")

    session_factory = get_session_factory()

    with session_factory() as session:
        logger.info("[Query 1] Find product by ID (no index)")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, name, price, category
            FROM products
            WHERE id = 25000
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")

        logger.info("\n[Query 2] Find products by category (no index)")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, name, price
            FROM products
            WHERE category = 'Electronics'
            LIMIT 100
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")


def create_btree_index_on_id() -> None:
    """Create standard B-Tree index on primary key."""
    print_separator("CREATING B-TREE INDEX ON ID")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Note: Primary key already has an index, but we'll measure it
        logger.info("[Note] Primary key 'id' already has a B-Tree index")

        # Show the index
        result = session.execute(
            text("""
            SELECT
                indexrelname,
                pg_size_pretty(pg_relation_size(indexrelid)) as size
            FROM pg_stat_user_indexes
            WHERE relname = 'products' AND indexrelname LIKE '%pkey%'
        """)
        )

        for row in result:
            logger.info(f"[Index] {row[0]}: {row[1]}")


def test_index_scan_on_id() -> None:
    """Demonstrate index scan with B-Tree index."""
    print_separator("INDEX SCAN: Using B-Tree Index on ID")

    session_factory = get_session_factory()

    with session_factory() as session:
        logger.info("[Query] Find product by ID (with index)")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, name, price, category
            FROM products
            WHERE id = 25000
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")

        logger.info("\n[Observation] Notice the query plan changed from Seq Scan to Index Scan")
        logger.info("[Performance] Index Scan is much faster for point lookups")


def create_btree_index_on_category() -> None:
    """Create B-Tree index on category column."""
    print_separator("CREATING B-TREE INDEX ON CATEGORY")

    session_factory = get_session_factory()

    with session_factory() as session:
        start_time = time.time()

        session.execute(
            text("""
            CREATE INDEX idx_products_category
            ON products(category)
        """)
        )
        session.commit()

        elapsed = time.time() - start_time
        logger.info(f"[Created] B-Tree index in {elapsed:.2f}s")

        # Show index size
        result = session.execute(
            text("""
            SELECT pg_size_pretty(pg_relation_size('idx_products_category'))
        """)
        )
        size = result.fetchone()[0]
        logger.info(f"[Index Size] {size}")


def test_index_scan_on_category() -> None:
    """Test queries with category index."""
    print_separator("INDEX SCAN: Using B-Tree Index on Category")

    session_factory = get_session_factory()

    with session_factory() as session:
        logger.info("[Query] Find products by category (with index)")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, name, price
            FROM products
            WHERE category = 'Electronics'
            LIMIT 100
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")


def demonstrate_btree_structure() -> None:
    """Explain B-Tree structure and characteristics."""
    print_separator("B-TREE INDEX CHARACTERISTICS")

    logger.info("\n[Structure] B-Tree (Balanced Tree)")
    logger.info("  • Self-balancing tree structure")
    logger.info("  • Keys stored in sorted order")
    logger.info("  • Logarithmic search time: O(log n)")
    logger.info("  • Efficient for: =, <, >, <=, >=, BETWEEN, IN")

    logger.info("\n[How It Works]")
    logger.info("  1. Root node points to intermediate nodes")
    logger.info("  2. Intermediate nodes guide search to leaf nodes")
    logger.info("  3. Leaf nodes contain actual row pointers")
    logger.info("  4. All leaf nodes are at the same depth (balanced)")

    logger.info("\n[When PostgreSQL Uses the Index]")
    logger.info("  • Selective queries (small % of rows)")
    logger.info("  • Point lookups (WHERE id = X)")
    logger.info("  • Range queries (WHERE created_at > X)")
    logger.info("  • Sorted output (ORDER BY indexed_column)")

    logger.info("\n[When PostgreSQL Ignores the Index]")
    logger.info("  • Query returns large % of table (Seq Scan faster)")
    logger.info("  • Statistics are outdated (run ANALYZE)")
    logger.info("  • Table is very small (<10K rows typically)")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Show index statistics
        result = session.execute(
            text("""
            SELECT
                schemaname,
                relname,
                indexrelname,
                pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
                idx_scan AS scans,
                idx_tup_read AS tuples_read
            FROM
                pg_stat_user_indexes
            WHERE
                relname = 'products'
            ORDER BY
                indexrelname
        """)
        )

        logger.info("\n[Current Indexes on products table]")
        for row in result:
            logger.info(f"  {row[2]}: {row[3]}, Scans: {row[4]}, Tuples Read: {row[5]}")


def compare_scan_types() -> None:
    """Compare different scan types with EXPLAIN output."""
    print_separator("SCAN TYPE COMPARISON")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Selective query (uses index)
        logger.info("[Test 1] Selective query - single product by ID")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT * FROM products WHERE id = 1000
        """)
        )
        for row in result:
            logger.info(f"  {row[0]}")

        # Non-selective query (may use Seq Scan)
        logger.info("\n[Test 2] Non-selective query - all active products")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT * FROM products WHERE active = true
        """)
        )
        for row in result:
            logger.info(f"  {row[0]}")

        logger.info("\n[Insight] PostgreSQL's query planner is cost-based")
        logger.info("It chooses Index Scan vs Seq Scan based on estimated cost")


def main() -> None:
    """Main entry point for Lab Step 0."""
    logger.info("=" * 60)
    logger.info("LAB STEP 0: B-Tree Index Fundamentals")
    logger.info("=" * 60)

    # Initialize database
    logger.info("\n[Phase 1] Initializing database...")
    init_db()

    # Generate test data
    logger.info("\n[Phase 2] Generating test data...")
    generate_sample_products(50000)

    # Show initial stats
    show_table_stats()

    # Test sequential scan
    logger.info("\n[Phase 3] Testing queries without indexes...")
    test_sequential_scan()

    # Show primary key index
    logger.info("\n[Phase 4] Examining default primary key index...")
    create_btree_index_on_id()
    test_index_scan_on_id()

    # Create index on category
    logger.info("\n[Phase 5] Creating B-Tree index on category...")
    create_btree_index_on_category()
    test_index_scan_on_category()

    # Explain B-Tree characteristics
    logger.info("\n[Phase 6] Understanding B-Tree structure...")
    demonstrate_btree_structure()

    # Compare scan types
    logger.info("\n[Phase 7] Comparing scan types...")
    compare_scan_types()

    logger.info("\n" + "=" * 60)
    logger.info("Lab Step 0 Complete!")
    logger.info("=" * 60)
    logger.info("\n[Key Insight] B-Tree is PostgreSQL's default and most versatile index type.")
    logger.info("It provides O(log n) lookup time for equality and range queries.")
    logger.info("Understanding B-Tree behavior is essential before exploring specialized indexes.")


if __name__ == "__main__":
    main()
