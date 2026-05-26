"""
Lab Step 1: JSONB vs. Normalization (Document Storage vs. Structured)

This script demonstrates:
- The performance and storage tradeoffs of three product catalog designs:
  1. Relational (Fully Normalized)
  2. EAV (Entity-Attribute-Value)
  3. JSONB (Semi-Structured Document)
- Querying JSONB documents using containment (@>) and path operators (->>)
- Accelerating JSONB searches using GIN indexes
- Under-the-hood execution plans (Seq Scan vs. Bitmap Index Scan)
"""

import time

from app.dependencies import get_session_factory, init_db
from app.models import ProductEAV, ProductEAVAttribute, ProductJSONB, ProductRelational
from faker import Faker
from loguru import logger
from sqlalchemy import text


fake = Faker()
Faker.seed(12345)


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def generate_sample_products(count: int = 20000) -> None:
    """Generate sample products across all three database schemas."""
    print_separator(f"GENERATING {count:,} SAMPLE PRODUCTS ACROSS SCHEMAS")

    session_factory = get_session_factory()
    batch_size = 5000

    categories = ["Electronics", "Clothing", "Home & Garden", "Books", "Sports", "Toys"]
    brands = ["Sony", "Apple", "Samsung", "Google", "Microsoft", "LG", "Sony", "Dell", "HP"]
    colors = ["red", "blue", "black", "white", "silver"]

    with session_factory() as session:
        for i in range(0, count, batch_size):
            rel_batch = []
            eav_batch = []
            jsonb_batch = []

            for j in range(batch_size):
                product_idx = i + j
                if product_idx >= count:
                    break

                # Common variables
                name = fake.catch_phrase()
                category = fake.random.choice(categories)
                price = fake.random.randint(500, 50000)  # $5 to $500
                brand = fake.random.choice(brands)
                color = fake.random.choice(colors)
                weight = round(fake.random.uniform(0.1, 50.0), 2)
                features = fake.random.choices(
                    ["wireless", "bluetooth", "waterproof", "rechargeable", "portable"],
                    k=fake.random.randint(1, 3),
                )

                # 1. Relational
                rel_prod = ProductRelational(
                    id=product_idx + 1,
                    name=name,
                    price=price,
                    brand=brand,
                    color=color,
                    weight_kg=weight,
                )
                rel_batch.append(rel_prod)

                # 2. EAV
                eav_prod = ProductEAV(id=product_idx + 1, name=name, price=price)
                eav_batch.append(eav_prod)

                # 3. JSONB
                jsonb_prod = ProductJSONB(
                    id=product_idx + 1,
                    name=name,
                    price=price,
                    attributes={
                        "brand": brand,
                        "color": color,
                        "weight_kg": weight,
                        "features": features,
                        "category": category,
                    },
                )
                jsonb_batch.append(jsonb_prod)

            # Insert all
            session.add_all(rel_batch)
            session.add_all(eav_batch)
            session.add_all(jsonb_batch)
            session.commit()

            # Now insert EAV attributes (needs foreign keys to be committed)
            eav_attrs = []
            for j in range(batch_size):
                product_idx = i + j
                if product_idx >= count:
                    break

                # Generate attributes
                brand = jsonb_batch[j].attributes["brand"]
                color = jsonb_batch[j].attributes["color"]
                weight = str(jsonb_batch[j].attributes["weight_kg"])
                category = jsonb_batch[j].attributes["category"]

                # Add EAV mappings
                eav_attrs.append(ProductEAVAttribute(product_id=product_idx + 1, key="brand", value=brand))
                eav_attrs.append(ProductEAVAttribute(product_id=product_idx + 1, key="color", value=color))
                eav_attrs.append(ProductEAVAttribute(product_id=product_idx + 1, key="weight_kg", value=weight))
                eav_attrs.append(ProductEAVAttribute(product_id=product_idx + 1, key="category", value=category))

            session.add_all(eav_attrs)
            session.commit()

            logger.info(f"[Progress] Inserted {min(i + batch_size, count):,} / {count:,} products")

    # Run ANALYZE to update statistics
    with session_factory() as session:
        session.execute(text("ANALYZE products_relational"))
        session.execute(text("ANALYZE products_eav"))
        session.execute(text("ANALYZE product_eav_attributes"))
        session.execute(text("ANALYZE products_jsonb"))
        session.commit()

    logger.info(f"[Complete] Generated {count:,} products across all schemas")


def compare_storage_size() -> None:
    """Analyze and compare disk storage footprints of each design."""
    print_separator("STORAGE FOOTPRINT COMPARISON")

    session_factory = get_session_factory()

    with session_factory() as session:
        result = session.execute(
            text("""
            SELECT
                'Relational' as model,
                pg_size_pretty(pg_total_relation_size('products_relational')) as total_size,
                pg_size_pretty(pg_relation_size('products_relational')) as table_size
            UNION ALL
            SELECT
                'EAV Pattern' as model,
                pg_size_pretty(pg_total_relation_size('products_eav') +
                               pg_total_relation_size('product_eav_attributes')) as total_size,
                pg_size_pretty(pg_relation_size('products_eav') +
                               pg_relation_size('product_eav_attributes')) as table_size
            UNION ALL
            SELECT
                'JSONB Document' as model,
                pg_size_pretty(pg_total_relation_size('products_jsonb')) as total_size,
                pg_size_pretty(pg_relation_size('products_jsonb')) as table_size
        """)
        )

        logger.info("[Storage Sizes]")
        for row in result:
            logger.info(f"  Model: {row[0]:<15} Total size: {row[1]:<10} (Table Data: {row[2]})")

        logger.info(
            "==> [Key Insight] EAV is highly bloated due to row overhead and duplicate keys in index/table structures."
        )
        logger.info(
            "==> [Key Insight] JSONB is compact and self-contained, but slightly larger than normalized columns due to repeating key metadata inside values."
        )


def test_queries_without_indexes() -> None:
    """Run baseline query benchmarks on unindexed tables."""
    print_separator("BASELINE QUERY PERFORMANCE (NO INDEXES)")

    session_factory = get_session_factory()

    with session_factory() as session:
        # 1. Relational
        logger.info("[Query 1] Relational lookup: brand = 'Sony' AND color = 'red'")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, name, price
            FROM products_relational
            WHERE brand = 'Sony' AND color = 'red'
            LIMIT 10
        """)
        )
        for row in result:
            logger.info(f"  {row[0]}")

        # 2. EAV
        logger.info("[Query 2] EAV lookup: brand = 'Sony' AND color = 'red'")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT p.id, p.name, p.price
            FROM products_eav p
            JOIN product_eav_attributes a1 ON p.id = a1.product_id AND a1.key = 'brand' AND a1.value = 'Sony'
            JOIN product_eav_attributes a2 ON p.id = a2.product_id AND a2.key = 'color' AND a2.value = 'red'
            LIMIT 10
        """)
        )
        for row in result:
            logger.info(f"  {row[0]}")

        # 3. JSONB Containment (@>)
        logger.info('[Query 3] JSONB Containment lookup: attributes @> \'{"brand": "Sony", "color": "red"}\'')
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, name, price
            FROM products_jsonb
            WHERE attributes @> '{"brand": "Sony", "color": "red"}'
            LIMIT 10
        """)
        )
        for row in result:
            logger.info(f"  {row[0]}")


def create_and_test_jsonb_gin_index() -> None:
    """Create a GIN index on JSONB and benchmark queries."""
    print_separator("GIN INDEX BENCHMARK & EXECUTION PLANS")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Create GIN index
        logger.info("[Action] Creating standard GIN index on JSONB attributes...")
        start_time = time.time()
        session.execute(text("CREATE INDEX idx_products_jsonb_gin ON products_jsonb USING GIN (attributes)"))
        session.commit()
        session.execute(text("ANALYZE products_jsonb"))
        session.commit()
        logger.info(f"[Created] GIN Index in {time.time() - start_time:.2f}s")

        # Query index stats size
        size_res = session.execute(text("SELECT pg_size_pretty(pg_relation_size('idx_products_jsonb_gin'))"))
        logger.info(f"[Index Size] GIN size: {size_res.fetchone()[0]}")

        # Force GIN usage by disabling sequential scans for demonstration
        session.execute(text("SET enable_seqscan = off"))

        # Re-test GIN query
        logger.info("[Query 4] JSONB Containment query WITH GIN Index:")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, name, price
            FROM products_jsonb
            WHERE attributes @> '{"brand": "Sony", "color": "red"}'
            LIMIT 10
        """)
        )
        for row in result:
            logger.info(f"  {row[0]}")

        # Test extraction operator ->> (Observe why GIN index is ignored!)
        logger.info("[Query 5] JSONB extraction query WITH GIN Index using ->> operator (Observe plan!):")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT id, name, price
            FROM products_jsonb
            WHERE attributes->>'brand' = 'Sony' AND attributes->>'color' = 'red'
            LIMIT 10
        """)
        )
        for row in result:
            logger.info(f"  {row[0]}")

        session.execute(text("SET enable_seqscan = on"))


def main() -> None:
    """Main entry point for Step 1."""
    logger.info("=" * 60)
    logger.info("LAB STEP 1: JSONB vs. Normalization")
    logger.info("=" * 60)

    logger.info("==> [Phase 1] Initializing database...")
    init_db()

    # Generate test data
    logger.info("==> [Phase 2] Generating product catalogs...")
    generate_sample_products(20000)

    # Compare sizes
    logger.info("==> [Phase 3] Comparing storage sizes...")
    compare_storage_size()

    # Test baseline queries
    logger.info("==> [Phase 4] Testing queries without indexes...")
    test_queries_without_indexes()

    # Create GIN index and test plans
    logger.info("==> [Phase 5] Creating and testing GIN indexing...")
    create_and_test_jsonb_gin_index()

    logger.info("=" * 60)
    logger.info("Lab Step 1 Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
