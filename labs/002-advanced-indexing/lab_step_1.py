"""
Lab Step 1: Partial Indexes

This script demonstrates:
- Partial indexes to reduce index size and maintenance overhead
- Performance comparison between full and partial indexes
- When to use partial indexes in production

Note: This step reuses product data from Step 0. If you haven't run Step 0,
this script will generate the necessary data automatically.
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
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def generate_sample_products(count: int = 50000) -> None:
    """
    Generate sample product data with realistic distribution:
    - 15% active products (hot/current inventory)
    - 85% inactive products (archived/discontinued)
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

                # 15% active, 85% inactive (typical for archived product catalogs)
                is_active = fake.random.random() < 0.15

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
                            ["wireless", "bluetooth", "waterproof", "rechargeable", "portable"],
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
    """Display table and index statistics."""
    print_separator("TABLE & INDEX STATISTICS")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Table size
        result = session.execute(
            text("""
            SELECT
                pg_size_pretty(pg_total_relation_size('products')) as total_size,
                pg_size_pretty(pg_relation_size('products')) as table_size,
                pg_size_pretty(pg_total_relation_size('products') - pg_relation_size('products')) as indexes_size
        """)
        )
        row = result.fetchone()
        logger.info(f"[Table Size] Total: {row[0]}, Data: {row[1]}, Indexes: {row[2]}")

        # Row counts
        total = session.query(Product).count()
        active = session.query(Product).filter(Product.active).count()
        inactive = session.query(Product).filter(~Product.active).count()

        logger.info(
            f"[Row Counts] Total: {total:,}, Active: {active:,} ({100 * active / total:.1f}%), Inactive: {inactive:,} ({100 * inactive / total:.1f}%)"
        )


def test_query_without_index() -> None:
    """Test query performance without specialized indexes."""
    print_separator("BASELINE: Query Active Products (No Partial Index)")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Use EXPLAIN ANALYZE to see actual execution
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, category, price
            FROM products
            WHERE active = true
            ORDER BY category, price
            LIMIT 100
        """)
        )

        logger.info("[EXPLAIN Output]")
        for row in result:
            logger.info(f"  {row[0]}")


def create_partial_index() -> None:
    """Create a partial index on active products only."""
    print_separator("CREATING PARTIAL INDEX")

    session_factory = get_session_factory()

    with session_factory() as session:
        start_time = time.time()

        session.execute(
            text("""
            CREATE INDEX idx_products_active
            ON products(id, category, price)
            WHERE active = true
        """)
        )
        session.commit()

        elapsed = time.time() - start_time
        logger.info(f"[Created] Partial index in {elapsed:.2f}s")

        # Update statistics so PostgreSQL knows about the index
        logger.info("[Updating] Table statistics...")
        session.execute(text("ANALYZE products"))
        session.commit()
        logger.info("[Complete] Statistics updated")

        # Show index size
        result = session.execute(
            text("""
            SELECT pg_size_pretty(pg_relation_size('idx_products_active'))
        """)
        )
        size = result.fetchone()[0]
        logger.info(f"[Index Size] {size}")


def test_query_with_partial_index() -> None:
    """Test the same query with the partial index."""
    print_separator("WITH PARTIAL INDEX: Query Active Products")

    session_factory = get_session_factory()

    with session_factory() as session:
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, category, price
            FROM products
            WHERE active = true
            ORDER BY category, price
            LIMIT 100
        """)
        )

        logger.info("[EXPLAIN Output]")
        for row in result:
            logger.info(f"  {row[0]}")


def compare_full_vs_partial_index() -> None:
    """Compare a full B-tree index vs partial index."""
    print_separator("COMPARISON: Full Index vs Partial Index")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Create full index for comparison (same columns as partial index)
        logger.info("[Creating] Full B-tree index on (id, category, price)...")
        start_time = time.time()

        session.execute(text("CREATE INDEX idx_products_active_full ON products(id, category, price)"))
        session.commit()

        elapsed = time.time() - start_time
        logger.info(f"[Created] Full index in {elapsed:.2f}s")

        # Compare sizes
        result = session.execute(
            text("""
            SELECT
                'Full Index' as index_type,
                pg_size_pretty(pg_relation_size('idx_products_active_full')) as size
            UNION ALL
            SELECT
                'Partial Index' as index_type,
                pg_size_pretty(pg_relation_size('idx_products_active')) as size
        """)
        )

        logger.info("[Index Size Comparison]")
        for row in result:
            logger.info(f"  {row[0]}: {row[1]}")

        # Drop the full index (not needed)
        session.execute(text("DROP INDEX idx_products_active_full"))
        session.commit()
        logger.info("[Cleanup] Dropped full index")


def main() -> None:
    """Main entry point for Lab Step 1."""
    logger.info("=" * 60)
    logger.info("LAB STEP 1: Partial Indexes")
    logger.info("=" * 60)

    logger.info("==> [Phase 1] Initializing database...")
    init_db()
    logger.info("==> [Phase 2] Generating test data...")
    generate_sample_products(50000)

    # Show initial stats
    show_table_stats()

    # Test without index
    logger.info("==> [Phase 3] Testing query without partial index...")
    test_query_without_index()

    # Create partial index
    logger.info("==> [Phase 4] Creating partial index...")
    create_partial_index()

    # Test with partial index
    logger.info("==> [Phase 5] Testing query with partial index...")
    test_query_with_partial_index()

    # Compare full vs partial
    logger.info("==> [Phase 6] Comparing full vs partial index...")
    compare_full_vs_partial_index()

    logger.info("" + "=" * 60)
    logger.info("Lab Step 1 Complete!")
    logger.info("=" * 60)
    logger.info("==> [Key Insight] Partial indexes reduce storage and maintenance costs")
    logger.info("while providing identical performance for filtered queries.")


if __name__ == "__main__":
    main()
