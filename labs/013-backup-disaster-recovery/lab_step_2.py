import time

from app.dependencies import get_db_engine, get_session_factory
from app.models import UserAccount
from loguru import logger
from sqlalchemy import select, text


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def main():
    print_separator("STEP 2: TRANSACTIONS & DISASTER SIMULATION")

    engine = get_db_engine()
    session_factory = get_session_factory()

    # 1. Insert Bob (before target recovery point)
    logger.info("Inserting record: Bob...")
    with session_factory() as session:
        bob = UserAccount(username="bob", balance=200.0)
        session.add(bob)
        session.commit()
        logger.info(f"Persisted: {bob}")

    # 2. Get target timestamp from the database
    with engine.connect() as conn:
        # Get DB current time to have exact timezone alignment
        db_now = conn.execute(text("SELECT NOW()")).scalar()

    logger.info(f"Recording Recovery Target Timestamp (T1): {db_now}")
    with open("recovery_target.txt", "w") as f:
        f.write(str(db_now))

    # Sleep slightly to separate timestamps clearly
    logger.info("Waiting 3 seconds before next transaction...")
    time.sleep(3)

    # 3. Insert Charlie (after target recovery point - this record will be lost in recovery)
    logger.info("Inserting record: Charlie (post-recovery-target)...")
    with session_factory() as session:
        charlie = UserAccount(username="charlie", balance=300.0)
        session.add(charlie)
        session.commit()
        logger.info(f"Persisted: {charlie}")

    # Forcing a WAL switch to ensure Charlie and Bob are flushed to archived logs
    logger.info("Forcing WAL switch to archive logs...")
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_switch_wal()"))

    # 4. Simulate a disaster (Drop Table)
    print_separator("DISASTER STRIKES!")
    logger.info("Simulating accidental DROP TABLE disaster...")
    with engine.connect() as conn:
        # We need to end any transaction block
        conn.execute(text("DROP TABLE user_accounts CASCADE"))
        conn.commit()
    logger.warning("Table 'user_accounts' has been DROPPED!")

    # Verify query fails
    logger.info("Attempting to query table 'user_accounts'...")
    try:
        with session_factory() as session:
            session.execute(select(UserAccount)).all()
        logger.error("[Failure] Table query succeeded? It should have failed!")
    except Exception as e:
        logger.info("SUCCESS: Query failed as expected. Database is in a corrupted/disaster state.")
        logger.info(f"  * Exception message: {e}")

    print_separator("DISASTER METRICS")
    logger.info("Recovery Point Objective (RPO):")
    logger.info("  * Represents maximum acceptable data loss.")
    logger.info("  * With WAL archiving, we can recover right up to T1 (just before the drop table query).")
    logger.info("Recovery Time Objective (RTO):")
    logger.info("  * Represents maximum acceptable downtime.")
    logger.info("  * Physical recovery requires stopping PG, restoring files, and replaying WAL logs.")

    logger.info("=" * 60)
    logger.info("Lab Step 2 Complete! Next, run lab_step_3.py to restore.")


if __name__ == "__main__":
    main()
