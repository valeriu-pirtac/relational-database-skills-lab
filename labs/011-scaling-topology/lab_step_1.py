import time

from app.dependencies import get_primary_engine, get_replica_engine, init_db
from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def check_recovery_status(engine, name: str) -> bool:
    """Queries pg_is_in_recovery() on the given engine."""
    with engine.connect() as conn:
        res = conn.execute(text("SELECT pg_is_in_recovery()")).scalar()
        logger.info(f"[{name}] pg_is_in_recovery() = {res}")
        return bool(res)


def main():
    print_separator("STEP 1: PHYSICAL REPLICATION VERIFICATION")

    primary_engine = get_primary_engine()
    replica_engine = get_replica_engine()

    # 1. Test database connections and init tables
    init_db()

    # 2. Verify roles (Primary = Writer, Replica = Reader)
    logger.info("Verifying replication node roles...")
    is_primary_recovery = check_recovery_status(primary_engine, "Primary Node")
    is_replica_recovery = check_recovery_status(replica_engine, "Replica Node")

    if is_primary_recovery:
        logger.error("[Error] Primary node is in recovery mode! It should be a writer.")
    if not is_replica_recovery:
        logger.error("[Error] Replica node is NOT in recovery mode! It should be a reader.")

    # 3. Test replication data flow
    print_separator("TESTING REPLICATION DATA FLOW")

    # Insert on primary
    logger.info("[Primary] Inserting a new user...")
    with primary_engine.connect() as conn:
        conn.execute(
            text("INSERT INTO user_accounts (username, balance) VALUES (:u, :b)"),
            {"u": "replication_test_user", "b": 500.0},
        )
        conn.commit()
    logger.info("[Primary] Insert committed.")

    # Immediately query on replica to see replication speed
    logger.info("[Replica] Querying replica node for the new user...")
    time.sleep(0.1)  # small sleep to allow async stream to catch up if needed
    with replica_engine.connect() as conn:
        res = conn.execute(
            text("SELECT username, balance FROM user_accounts WHERE username = :u"),
            {"u": "replication_test_user"},
        ).fetchone()

        if res:
            logger.info(f"[Replica] SUCCESS! Found replicated row: username='{res[0]}', balance={res[1]}")
        else:
            logger.error("[Replica] FAILED! Row did not replicate in time.")

    # 4. Prove Replica is Read-Only
    print_separator("PROVING REPLICA IS READ-ONLY")
    logger.info("[Replica] Attempting to write directly to Replica node...")
    try:
        with replica_engine.connect() as conn:
            conn.execute(
                text("INSERT INTO user_accounts (username, balance) VALUES (:u, :b)"),
                {"u": "should_fail", "b": 100.0},
            )
            conn.commit()
        logger.error("[Replica] FAILED! Expected a ReadOnlySqlTransaction error, but write succeeded?!")
    except DBAPIError as e:
        # PostgreSQL should raise: ERROR: cannot execute INSERT in a read-only transaction
        logger.info("[Replica] SUCCESS! Prevented write operation. Caught expected error:")
        logger.info(f"  * Exception type: {type(e).__name__}")
        logger.info(f"  * Error message : {str(e.orig).strip()}")

    # 5. Check replication diagnostics from Primary
    print_separator("REPLICATION STATS FROM PRIMARY")
    with primary_engine.connect() as conn:
        stats = conn.execute(
            text(
                "SELECT client_addr, state, sync_state, "
                "pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS lag_bytes "
                "FROM pg_stat_replication"
            )
        ).fetchall()

        if stats:
            for s in stats:
                logger.info(f"  * Connected Replica IP: {s[0]}")
                logger.info(f"  * Replication State   : {s[1]}")
                logger.info(f"  * Sync Mode           : {s[2]}")
                logger.info(f"  * Lag (bytes)         : {s[3]} bytes")
        else:
            logger.warning(
                "[Primary] No replica clients found in pg_stat_replication. Check if replica container is up."
            )

    logger.info("=" * 60)
    logger.info("Lab Step 1 Complete!")


if __name__ == "__main__":
    main()
