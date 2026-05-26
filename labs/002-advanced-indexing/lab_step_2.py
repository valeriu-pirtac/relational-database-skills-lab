"""
Lab Step 2: GIN Indexes for JSONB and Full-Text Search

This script demonstrates:
- GIN (Generalized Inverted Index) for JSONB columns
- GIN for full-text search with tsvector
- Performance comparison with and without GIN indexes
- Different JSONB query operators (@>, ?, ->, ->>)
"""

import time

from app.dependencies import get_session_factory, init_db
from app.models import Article, Product
from faker import Faker
from loguru import logger
from sqlalchemy import text


fake = Faker()
Faker.seed(123)


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def generate_sample_articles(count: int = 10000) -> None:
    """Generate sample articles with full-text content."""
    print_separator(f"GENERATING {count:,} SAMPLE ARTICLES")

    session_factory = get_session_factory()
    batch_size = 1000

    tech_topics = [
        "postgresql",
        "database",
        "performance",
        "optimization",
        "indexing",
        "query",
        "transaction",
        "replication",
        "backup",
        "security",
    ]

    with session_factory() as session:
        for i in range(0, count, batch_size):
            articles = []
            for j in range(batch_size):
                if i + j >= count:
                    break

                # Generate article with tech-related content
                title = fake.catch_phrase()
                content_parts = [fake.paragraph(nb_sentences=5) for _ in range(3)]

                # Inject some tech terms randomly
                for part in content_parts:
                    if fake.random.random() < 0.3:
                        part += f" {fake.random.choice(tech_topics)}"

                content = " ".join(content_parts)

                article = Article(
                    title=title,
                    author=fake.name(),
                    content=content,
                    tags=fake.random.choices(
                        ["database", "python", "postgresql", "tutorial", "guide", "advanced"],
                        k=fake.random.randint(2, 4),
                    ),
                    published=fake.random.random() < 0.8,
                )
                articles.append(article)

            session.add_all(articles)
            session.commit()
            logger.info(f"[Progress] Inserted {min(i + batch_size, count):,} / {count:,} articles")
        logger.info("[Processing] Generating full-text search vectors...")
        session.execute(
            text("""
            UPDATE articles
            SET search_vector = to_tsvector('english', title || ' ' || content)
        """)
        )
        session.commit()

    # Run ANALYZE to update statistics
    with session_factory() as session:
        session.execute(text("ANALYZE articles"))
        session.commit()

    logger.info(f"[Complete] Generated {count:,} articles with search vectors")


def generate_sample_products(count: int = 10000) -> None:
    """Generate sample products with realistic JSONB attributes."""
    print_separator(f"GENERATING {count:,} SAMPLE PRODUCTS")

    session_factory = get_session_factory()
    batch_size = 2000

    categories = ["Electronics", "Clothing", "Home & Garden", "Books", "Sports", "Toys"]
    brands = ["Sony", "Apple", "Samsung", "Google", "Microsoft", "LG", "Sony", "Dell", "HP"]

    with session_factory() as session:
        for i in range(0, count, batch_size):
            products = []
            for j in range(batch_size):
                if i + j >= count:
                    break

                # Generate attributes
                brand = fake.random.choice(brands)
                color = fake.random.choice(["red", "blue", "black", "white", "silver"])
                features = fake.random.choices(
                    ["wireless", "bluetooth", "waterproof", "rechargeable", "portable"],
                    k=fake.random.randint(1, 3),
                )

                product = Product(
                    name=fake.catch_phrase(),
                    category=fake.random.choice(categories),
                    description=fake.text(max_nb_chars=200),
                    price=fake.random.randint(500, 50000),  # $5 to $500
                    active=fake.random.random() < 0.7,
                    attributes={
                        "brand": brand,
                        "color": color,
                        "features": features,
                        "weight_kg": round(fake.random.uniform(0.1, 50.0), 2),
                        "dimensions": {
                            "length": fake.random.randint(10, 200),
                            "width": fake.random.randint(10, 200),
                            "height": fake.random.randint(10, 200),
                        },
                    },
                )
                products.append(product)

            session.add_all(products)
            session.commit()
            logger.info(f"[Progress] Inserted {min(i + batch_size, count):,} / {count:,} products")

    # Run ANALYZE to update statistics
    with session_factory() as session:
        session.execute(text("ANALYZE products"))
        session.commit()

    logger.info(f"[Complete] Generated {count:,} products")


def test_jsonb_query_without_index() -> None:
    """Test JSONB queries without GIN index."""
    print_separator("BASELINE: JSONB Query (No GIN Index)")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Test containment operator (@>)
        logger.info("[Query 1] Testing @> containment operator")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, name, attributes->>'color' as color
            FROM products
            WHERE attributes @> '{"color": "red"}'
            LIMIT 500
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")

        # Test path operator (->>)
        logger.info("\n[Query 2] Testing ->> path operator")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, name, attributes->>'features' as features
            FROM products
            WHERE attributes->>'features' = 'bluetooth'
            LIMIT 1000
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")


def create_gin_index_on_jsonb() -> None:
    """Create GIN index on JSONB column."""
    print_separator("CREATING GIN INDEX ON JSONB")

    session_factory = get_session_factory()

    with session_factory() as session:
        start_time = time.time()

        # Create GIN index on attributes column
        session.execute(
            text("""
            CREATE INDEX idx_products_attributes_gin
            ON products USING GIN (attributes)
        """)
        )
        session.commit()

        # Run ANALYZE to update statistics
        session.execute(text("ANALYZE products"))
        session.commit()

        elapsed = time.time() - start_time
        logger.info(f"[Created] GIN index on attributes in {elapsed:.2f}s")

        # Show index size
        result = session.execute(
            text("""
            SELECT pg_size_pretty(pg_relation_size('idx_products_attributes_gin'))
        """)
        )
        size = result.fetchone()[0]
        logger.info(f"[Index Size] {size}")


def test_jsonb_query_with_gin() -> None:
    """Test JSONB queries with GIN index."""
    print_separator("WITH GIN INDEX: JSONB Query Performance")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Disable sequential scans temporarily to force the planner to use the GIN index
        # session.execute(text("SET enable_seqscan = off"))

        # Test containment operator (@>)
        logger.info("[Query 1] Testing @> with GIN index")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, name, attributes->>'color' as color
            FROM products
            WHERE attributes @> '{"color": "red"}'
            LIMIT 500
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")

        # Test array containment
        logger.info("\n[Query 2] Testing array containment with GIN")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, name, attributes->'features' as features
            FROM products
            WHERE attributes @> '{"features": ["bluetooth"]}'
            LIMIT 1000
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")

        # Restore sequential scan setting
        # session.execute(text("SET enable_seqscan = on"))


def test_fulltext_without_gin() -> None:
    """Test full-text search without GIN index."""
    print_separator("BASELINE: Full-Text Search (No GIN Index)")

    session_factory = get_session_factory()

    with session_factory() as session:
        logger.info("[Query] Searching for 'postgresql & performance'")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, title, author
            FROM articles
            WHERE search_vector @@ to_tsquery('english', 'postgresql & performance')
            LIMIT 500
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")


def create_gin_index_on_tsvector() -> None:
    """Create GIN index on tsvector column for full-text search."""
    print_separator("CREATING GIN INDEX ON TSVECTOR")

    session_factory = get_session_factory()

    with session_factory() as session:
        start_time = time.time()

        session.execute(
            text("""
            CREATE INDEX idx_articles_search_vector_gin
            ON articles USING GIN (search_vector)
        """)
        )
        session.commit()

        # Run ANALYZE to update statistics
        session.execute(text("ANALYZE articles"))
        session.commit()

        elapsed = time.time() - start_time
        logger.info(f"[Created] GIN index on search_vector in {elapsed:.2f}s")

        # Show index size
        result = session.execute(
            text("""
            SELECT pg_size_pretty(pg_relation_size('idx_articles_search_vector_gin'))
        """)
        )
        size = result.fetchone()[0]
        logger.info(f"[Index Size] {size}")


def test_fulltext_with_gin() -> None:
    """Test full-text search with GIN index."""
    print_separator("WITH GIN INDEX: Full-Text Search Performance")

    session_factory = get_session_factory()

    with session_factory() as session:
        logger.info("[Query 1] Searching for 'postgresql & performance'")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, title, author
            FROM articles
            WHERE search_vector @@ to_tsquery('english', 'postgresql & performance')
            LIMIT 500
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")

        logger.info("\n[Query 2] Searching for 'database | optimization'")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, title, author
            FROM articles
            WHERE search_vector @@ to_tsquery('english', 'database | optimization')
            LIMIT 500
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")


def create_gin_index_on_jsonb_tags() -> None:
    """Create GIN index on JSONB array (tags)."""
    print_separator("CREATING GIN INDEX ON JSONB ARRAY")

    session_factory = get_session_factory()

    with session_factory() as session:
        start_time = time.time()

        session.execute(
            text("""
            CREATE INDEX idx_articles_tags_gin
            ON articles USING GIN (tags)
        """)
        )
        session.commit()

        # Run ANALYZE to update statistics
        session.execute(text("ANALYZE articles"))
        session.commit()

        elapsed = time.time() - start_time
        logger.info(f"[Created] GIN index on tags in {elapsed:.2f}s")

        # Disable sequential scans temporarily to force the planner to use the GIN index
        # session.execute(text("SET enable_seqscan = off"))

        # Test tag search
        logger.info("\n[Testing] Tag search with ? operator")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, title, tags
            FROM articles
            WHERE tags ? 'database'
            LIMIT 500
        """)
        )

        for row in result:
            logger.info(f"  {row[0]}")

        # Restore sequential scan setting
        # session.execute(text("SET enable_seqscan = on"))


def show_gin_index_stats() -> None:
    """Display statistics for all GIN indexes."""
    print_separator("GIN INDEX STATISTICS")

    session_factory = get_session_factory()

    with session_factory() as session:
        result = session.execute(
            text("""
            SELECT
                schemaname,
                relname,
                indexrelname,
                pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
                idx_scan AS number_of_scans,
                idx_tup_read AS tuples_read,
                idx_tup_fetch AS tuples_fetched
            FROM
                pg_stat_user_indexes
            WHERE
                indexrelname LIKE '%_gin'
            ORDER BY
                relname, indexrelname
        """)
        )

        logger.info("[GIN Indexes]")
        for row in result:
            logger.info(f"  Table: {row[1]}, Index: {row[2]}, Size: {row[3]}, Scans: {row[4]}")


def main() -> None:
    """Main entry point for Lab Step 2."""
    logger.info("=" * 60)
    logger.info("LAB STEP 2: GIN Indexes for JSONB and Full-Text Search")
    logger.info("=" * 60)

    logger.info("==> [Phase 0] Initializing database...")
    init_db()

    # Generate products and articles
    logger.info("==> [Phase 1] Generating test data...")
    generate_sample_products(10000)
    generate_sample_articles(10000)

    # Test JSONB without index
    logger.info("==> [Phase 2] Testing JSONB queries without GIN index...")
    test_jsonb_query_without_index()

    # Create GIN index on JSONB
    logger.info("==> [Phase 3] Creating GIN index on JSONB...")
    create_gin_index_on_jsonb()

    # Test JSONB with index
    logger.info("==> [Phase 4] Testing JSONB queries with GIN index...")
    test_jsonb_query_with_gin()

    # Test full-text search without index
    logger.info("==> [Phase 5] Testing full-text search without GIN index...")
    test_fulltext_without_gin()

    # Create GIN index on tsvector
    logger.info("==> [Phase 6] Creating GIN index on tsvector...")
    create_gin_index_on_tsvector()

    # Test full-text search with index
    logger.info("==> [Phase 7] Testing full-text search with GIN index...")
    test_fulltext_with_gin()

    # Create GIN index on tags
    logger.info("==> [Phase 8] Creating GIN index on JSONB array...")
    create_gin_index_on_jsonb_tags()

    # Show statistics
    logger.info("==> [Phase 9] Displaying GIN index statistics...")
    show_gin_index_stats()

    logger.info("=" * 60)
    logger.info("Lab Step 2 Complete!")
    logger.info("=" * 60)
    logger.info("==> [Key Insight] GIN indexes are essential for JSONB containment queries")
    logger.info("and full-text search, providing massive performance improvements.")


if __name__ == "__main__":
    main()
