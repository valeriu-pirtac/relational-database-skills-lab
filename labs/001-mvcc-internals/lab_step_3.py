import time
from decimal import Decimal

from app.dependencies import get_session_factory, init_db, insert_user
from app.models import User
from loguru import logger
from sqlalchemy import text


def setup_baseline():
    """Seed the database with a few control rows."""
    logger.info("==> [Seeding] Creating baseline user...")
    # Drop and recreate tables to ensure clean state
    init_db()
    insert_user("target_user", Decimal("100.00"))
    logger.info("==> [Seeding] Complete.")


def print_stat_user_tables(session):
    """Query postgres statistics views to see tuple counts."""
    query = text("""
        SELECT n_live_tup, n_dead_tup, last_vacuum, last_autovacuum
        FROM pg_stat_user_tables
        WHERE relname = 'users';
    """)
    result = session.execute(query).fetchone()
    if result:
        logger.info("\n[Postgres Stats] Table 'users':")
        logger.info(f"  * Live Tuples (Active Row Versions)  : {result[0]}")
        logger.info(f"  * Dead Tuples (Expired Row Versions)  : {result[1]}")
        logger.info(f"  * Last Manual Vacuum Runs            : {result[2]}")
        logger.info(f"  * Last Autovacuum Runs               : {result[3]}")


def print_physical_size(session):
    """Query the physical storage size of the table file on disk."""
    query = text("SELECT pg_size_pretty(pg_relation_size('users'));")
    size = session.execute(query).scalar()
    logger.info(f"  * Physical File Size on Disk         : {size}")


def run_update_flood(session, iterations=10000):
    """Perform rapid updates on a single row to generate massive dead tuple bloat."""
    logger.info(f"\n[Load] Starting flood of {iterations} UPDATE operations on ID=1...")

    # We update the balance of ID=1 repeatedly.
    # Because of MVCC, each update creates a new row version and leaves a dead tuple behind.
    start_time = time.time()

    # Run in a single transaction block for maximum speed
    user = session.query(User).filter_by(id=1).one()
    for i in range(iterations):
        user.balance += Decimal("0.01")  # Increment balance to trigger an update

        # Flush every 1000 updates to send them to Postgres disk pages
        if i % 1000 == 0:
            session.flush()

    session.commit()

    duration = time.time() - start_time
    logger.info(f"[Load] Finished update flood in {duration:.2f} seconds.")


def main():

    setup_baseline()
    session_local = get_session_factory()

    # 1. Setup baseline data and print initial stats
    with session_local() as session:
        logger.info("\n=== BEFORE FLOOD ===")
        # We need to run ANALYZE so that postgres statistics views (pg_stat_user_tables) are updated immediately
        session.execute(text("ANALYZE users;"))

        print_stat_user_tables(session)
        print_physical_size(session)

    # 2. Run the update flood to generate dead tuples
    with session_local() as session:
        # 1,000,000 updates will instantly produce 1,000,000 dead tuples on a single active row!
        run_update_flood(session, iterations=1000000)

        # We need to run ANALYZE so that postgres statistics views (pg_stat_user_tables) are updated immediately
        session.execute(text("ANALYZE users;"))
        session.commit()

    with session_local() as session:
        logger.info("\n=== AFTER FLOOD (Before Vacuum) ===")
        print_stat_user_tables(session)
        print_physical_size(session)

        logger.info(
            "[Notice] Observe how the dead tuple count is extremely high relative to the live tuple (which is just 1)!"
        )
        logger.info(
            "[Notice] In Step 4 of the lab, you will run manual VACUUM queries to inspect how these are cleaned up."
        )


if __name__ == "__main__":
    main()
