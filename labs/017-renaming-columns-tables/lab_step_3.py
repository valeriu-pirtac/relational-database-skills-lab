from app.dependencies import get_db_engine
from loguru import logger
from sqlalchemy import text


def main():
    engine = get_db_engine()

    # 1. CONTRACT PHASE: Clean up old database artifacts
    logger.info("=" * 20 + " CONTRACT PHASE: DROP ARTIFACTS " + "=" * 20)
    logger.info("Dropping database trigger...")
    with engine.begin() as conn:
        conn.execute(text("DROP TRIGGER IF EXISTS trg_sync_phone ON user_accounts"))

    logger.info("Dropping old column 'phone'...")
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE user_accounts DROP COLUMN phone"))
    logger.info("Trigger and 'phone' column dropped successfully.")

    # 2. Verify Database Columns Catalog
    logger.info("=" * 20 + " VERIFYING DATABASE CATALOG " + "=" * 20)
    with engine.connect() as conn:
        columns = conn.execute(
            text(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'user_accounts'
                ORDER BY ordinal_position
                """
            )
        ).fetchall()
        logger.info("Current Columns in 'user_accounts' table:")
        for col in columns:
            logger.info(f"  * Column: {col[0]} ({col[1]})")

    # 3. Verify Data Preservation
    logger.info("=" * 20 + " VERIFYING DATA PRESERVATION " + "=" * 20)
    logger.info("Fetching data using new column 'phone_number'...")
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, username, phone_number FROM user_accounts ORDER BY id")).fetchall()
        for r in rows:
            logger.info(f"  * User ID {r[0]:<2} | Username: {r[1]:<7} | phone_number: {r[2]}")

    logger.info("=" * 60)
    logger.info("Lab Step 3 Complete!")


if __name__ == "__main__":
    main()
