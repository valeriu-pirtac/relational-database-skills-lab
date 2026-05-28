"""
Lab Step 1: Connection Checkout Cycles & pool_pre_ping Connectivity Tests (Async Edition)

This script:
1. Initializes the database and seeds catalog products using sync connection.
2. Demonstrates the lifecycle of connection checkout and checkin events.
3. Simulates sudden server-side connection loss by executing `pg_terminate_backend` on Postgres.
4. Compares pool behavior with `pool_pre_ping=False` (raises OperationalError) vs
   `pool_pre_ping=True` (gracefully recycles and recovers silently).
"""

import asyncio

from app.dependencies import default_sync_engine, get_custom_engine, init_db
from app.models import Product
from loguru import logger
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import sessionmaker


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def seed_database(engine) -> None:
    """Seeds the catalog with basic products."""
    logger.info("[Seed] Seeding catalog products...")
    session_local = sessionmaker(bind=engine)
    with session_local() as session:
        p1 = Product(name="Developer Mechanical Keyboard", price=129.99, description="RGB Blue Switch Keyboard")
        p2 = Product(name="UltraWide Monitor 34-inch", price=450.00, description="144Hz curved screen")
        p3 = Product(name="Ergonomic Mesh Chair", price=299.99, description="High back lumbar support")
        session.add_all([p1, p2, p3])
        session.commit()
    logger.success("[Seed] Seeding complete.")


def kill_db_connections() -> None:
    """Simulates a database server restart or dropped connection by killing active backends."""
    logger.warning("[Database] Simulating sudden server-side connection drop...")

    # We use a separate, dedicated sync engine to execute the termination query
    killer_engine = get_custom_engine(pool_size=1, max_overflow=0, pool_pre_ping=False, is_async=False)
    session_local = sessionmaker(bind=killer_engine)
    with session_local() as session:
        kill_query = text("""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE pid <> pg_backend_pid()
              AND datname = 'pool_tuning';
        """)
        session.execute(kill_query)
        session.commit()
    killer_engine.dispose()
    logger.warning("[Database] All active pool connections terminated on the database server!")


async def test_without_pre_ping() -> None:
    """Tests pool recovery when pre-ping is DISABLED (Expects OperationalError)."""
    print_separator("TEST 1: pool_pre_ping=False (PREVENTABLE OUTAGE)")

    # Create async engine with pre-ping disabled
    engine = get_custom_engine(pool_size=2, max_overflow=0, pool_pre_ping=False, is_async=True)

    # 1. Warm up the pool by checking out and checking in a connection
    logger.info("[App] Checking out connection to run initial query...")
    async with engine.connect() as conn:
        result = (await conn.execute(select(Product))).all()
        logger.info(f"[App] Query success. Found {len(result)} products.")

    # The connection is now sitting idle inside the pool

    # 2. Simulate server-side dropped connection
    kill_db_connections()

    # 3. Attempt to run another query using the stale connection in the pool
    logger.info("[App] Attempting second query using the idle connection in the pool...")
    try:
        async with engine.connect() as conn:
            result = (await conn.execute(select(Product))).all()
            logger.success("[Success] Survived disconnect? (Unexpected without pre-ping!)")
    except (OperationalError, DBAPIError) as e:
        logger.error("[FAIL] Database OperationalError/DBAPIError caught as predicted!")
        logger.error(f"       Details: {str(e)[:150]}...")
        logger.warning("[FAIL] Without pre-ping, the app tried to reuse a dead connection and crashed.")
    finally:
        await engine.dispose()


async def test_with_pre_ping() -> None:
    """Tests pool recovery when pre-ping is ENABLED (Expects silent recovery)."""
    print_separator("TEST 2: pool_pre_ping=True (SILENT PRODUCTION RECOVERY)")

    # Create async engine with pre-ping enabled
    engine = get_custom_engine(pool_size=2, max_overflow=0, pool_pre_ping=True, is_async=True)

    # 1. Warm up the pool
    logger.info("[App] Checking out connection to run initial query...")
    async with engine.connect() as conn:
        result = (await conn.execute(select(Product))).all()
        logger.info(f"[App] Query success. Found {len(result)} products.")

    # Connection sits idle in the pool

    # 2. Simulate server-side dropped connection
    kill_db_connections()

    # 3. Attempt to run query again. With pre-ping, it should detect and recycle silently.
    logger.info("[App] Attempting second query. SQLAlchemy should execute pre-ping SELECT 1...")
    try:
        async with engine.connect() as conn:
            result = (await conn.execute(select(Product))).all()
            logger.success(f"[PASS] Silent recovery succeeded! Query completed cleanly. Found {len(result)} products.")
    except Exception as e:
        logger.error(f"[FAIL] Unexpected error occurred with pre-ping: {e}")
    finally:
        await engine.dispose()


async def async_main() -> None:
    logger.info("Initializing database...")
    init_db()

    # We use the default sync engine to seed the database first

    seed_database(default_sync_engine)

    # Run tests
    await test_without_pre_ping()
    logger.info("-" * 60)
    await test_with_pre_ping()

    logger.info("=" * 60)
    logger.info("Lab Step 1 Complete!")
    logger.info("=" * 60)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
