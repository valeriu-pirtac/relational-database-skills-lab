from app.dependencies import get_db_engine, init_db
from loguru import logger
from sqlalchemy import text


def run_migration_with_lock_timeout(ddl_sql: str, timeout_ms: int = 2000):
    """Simulates how Alembic runs migrations with a lock timeout context."""
    engine = get_db_engine()

    logger.info(f"Connecting to database to execute migration with lock_timeout = {timeout_ms}ms...")

    # In Alembic env.py, we wrap migration execution inside a transaction block
    with engine.begin() as conn:
        # 1. Inject the lock timeout configuration
        logger.info(f"Executing: SET lock_timeout = {timeout_ms}")
        conn.execute(text(f"SET lock_timeout = {timeout_ms}"))

        # 2. Execute the actual migration DDL statements
        logger.info(f"Executing DDL: {ddl_sql}")
        conn.execute(text(ddl_sql))

        logger.info("Migration transaction completed and committed.")


def main():
    logger.info("Initializing database...")
    init_db()

    # Scenario: Adding a column through a simulated Alembic migration context
    ddl_statement = "ALTER TABLE products ADD COLUMN tag VARCHAR(50)"

    try:
        run_migration_with_lock_timeout(ddl_statement, timeout_ms=1500)
        logger.info("[Success] Migration applied successfully within the lock timeout context!")
    except Exception as e:
        logger.error(f"[Failure] Migration failed: {e}")

    logger.info("Verify new schema layout:")
    engine = get_db_engine()
    with engine.connect() as conn:
        columns = conn.execute(
            text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'products'")
        ).fetchall()
        for col in columns:
            logger.info(f"  * Column: {col[0]} ({col[1]})")

    logger.info("=" * 60)
    logger.info("Lab Step 3 Complete!")


if __name__ == "__main__":
    main()
