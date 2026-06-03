from app.dependencies import get_db_engine, get_session_factory, init_db
from app.models import UserAccount
from loguru import logger
from sqlalchemy import text


def main():
    logger.info("Initializing database...")
    init_db()

    engine = get_db_engine()

    # 1. Simulate the "Before" state by dropping phone_number if it exists
    logger.info("[Before State] Dropping column 'phone_number' to simulate legacy schema...")
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE user_accounts DROP COLUMN IF EXISTS phone_number"))

    # 2. Seed initial data (old column only)
    logger.info("Seeding database with legacy user (Alice)...")
    session_factory = get_session_factory()
    with session_factory() as session:
        # We manually bypass ORM mapping for phone_number since the column doesn't exist yet
        session.execute(text("INSERT INTO user_accounts (username, phone) VALUES ('alice', '555-0101')"))
        session.commit()

    # Verify database state
    with engine.connect() as conn:
        res = conn.execute(text("SELECT * FROM user_accounts")).fetchone()
        logger.info(f"Database row: {res._mapping}")

    # 3. EXPAND PHASE: Add the new column as nullable
    logger.info("=" * 20 + " EXPAND PHASE: ADD COLUMN " + "=" * 20)
    logger.info("Adding column 'phone_number' as nullable...")
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE user_accounts ADD COLUMN phone_number VARCHAR(50) DEFAULT NULL"))
    logger.info("Column 'phone_number' added successfully.")

    # 4. Activate dual-writing at application level
    logger.info("=" * 20 + " TESTING DUAL-WRITING " + "=" * 20)
    logger.info("Inserting a new user (Bob) via the dual-writing ORM model...")
    with session_factory() as session:
        # The ORM event listener will copy phone -> phone_number
        bob = UserAccount(username="bob", phone="555-0202")
        session.add(bob)
        session.commit()
        logger.info(f"Persisted Bob: {bob}")

    # Verify both columns are populated in the database for Bob
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT username, phone, phone_number FROM user_accounts ORDER BY id")).fetchall()
        for r in rows:
            logger.info(f"  * User: {r[0]:<6} | phone (old): {r[1]:<10} | phone_number (new): {r[2]}")

    logger.info("=" * 60)
    logger.info("Lab Step 1 Complete!")


if __name__ == "__main__":
    main()
