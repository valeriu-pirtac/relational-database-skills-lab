from app.dependencies import get_db_engine
from loguru import logger
from sqlalchemy import text


def main():
    engine = get_db_engine()

    # 1. Backfill legacy data (Alice)
    logger.info("=" * 20 + " BACKFILLING LEGACY DATA " + "=" * 20)
    logger.info("Running update backfill for rows where phone_number is NULL...")

    with engine.begin() as conn:
        result = conn.execute(text("UPDATE user_accounts SET phone_number = phone WHERE phone_number IS NULL"))
        logger.info(f"Backfill complete. Updated {result.rowcount} records.")

    # 2. Database-level trigger setup
    logger.info("=" * 20 + " DATABASE TRIGGER SETUP " + "=" * 20)
    logger.info("Creating bidirectional sync trigger in PostgreSQL...")

    trigger_sql = """
    CREATE OR REPLACE FUNCTION sync_user_phone_fn()
    RETURNS TRIGGER AS $$
    BEGIN
        -- If phone changed, sync to phone_number
        IF (TG_OP = 'INSERT') OR (NEW.phone IS DISTINCT FROM OLD.phone) THEN
            NEW.phone_number := NEW.phone;
        -- If phone_number changed, sync to phone
        ELSIF NEW.phone_number IS DISTINCT FROM OLD.phone_number THEN
            NEW.phone := NEW.phone_number;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS trg_sync_phone ON user_accounts;
    CREATE TRIGGER trg_sync_phone
    BEFORE INSERT OR UPDATE ON user_accounts
    FOR EACH ROW
    EXECUTE FUNCTION sync_user_phone_fn();
    """

    with engine.begin() as conn:
        conn.execute(text(trigger_sql))
    logger.info("Sync trigger 'trg_sync_phone' created successfully.")

    # 3. Test database-level syncing
    logger.info("=" * 20 + " TESTING TRIGGER SYNC " + "=" * 20)
    logger.info("Executing raw SQL INSERT to test database-level sync...")

    # We execute raw SQL that only specifies the old 'phone' column
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO user_accounts (username, phone) VALUES ('charlie', '555-0303')"))

    # Verify trigger synced the column
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT username, phone, phone_number FROM user_accounts WHERE username = 'charlie'")
        ).fetchone()
        logger.info(f"Charlie database state: {row._mapping}")

        if row[1] == row[2] == "555-0303":
            logger.info("[Success] Database-level trigger successfully synced 'phone' to 'phone_number'!")
        else:
            logger.error("[Failure] Trigger sync failed.")

    logger.info("=" * 60)
    logger.info("Lab Step 2 Complete!")


if __name__ == "__main__":
    main()
