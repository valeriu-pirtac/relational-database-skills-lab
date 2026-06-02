import time

from app.dependencies import get_direct_engine, get_transaction_bouncer_engine, init_db
from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def show_active_advisory_locks(engine, label: str):
    """Queries pg_locks to show if any advisory locks are currently held by PostgreSQL."""
    with engine.connect() as conn:
        # objid is the lock ID we used
        result = conn.execute(
            text("SELECT pid, locktype, mode, granted FROM pg_locks WHERE locktype = 'advisory'")
        ).fetchall()
        logger.info(f"[{label}] Active advisory locks on PostgreSQL server:")
        if not result:
            logger.info("  * (None)")
        for row in result:
            logger.info(f"  * PID: {row[0]}, LockType: {row[1]}, Mode: {row[2]}, Granted: {row[3]}")


def test_temporary_tables_failure():
    print_separator("TEST 1: TEMPORARY TABLES BREAKAGE UNDER TRANSACTION POOLING")

    # Connect via PgBouncer in transaction mode
    engine = get_transaction_bouncer_engine(disable_prepared=True)

    logger.info("Opening client connections...")
    with engine.connect() as conn_a, engine.connect() as conn_b:
        trans_b = None
        trans_c = None
        conn_c = None
        try:
            # Transaction 1: Create a temp table
            import uuid

            table_name = f"temp_items_{uuid.uuid4().hex[:8]}"
            logger.info(f"Creating temporary table {table_name} in Transaction 1...")
            with conn_a.begin():
                conn_a.execute(text(f"CREATE TEMP TABLE IF NOT EXISTS {table_name} (id INT, name VARCHAR)"))
                conn_a.execute(text(f"INSERT INTO {table_name} VALUES (1, 'Widget')"))
                pid_1 = conn_a.execute(text("SELECT pg_backend_pid()")).scalar()
                logger.info(f"[Tx 1] Created {table_name} and inserted 1 row. (Backend PID: {pid_1})")

            # Occupy the backend connection that has the temp table
            logger.info("Client B starting Tx to occupy a backend connection...")
            trans_b = conn_b.begin()
            pid_b = conn_b.execute(text("SELECT pg_backend_pid()")).scalar()
            logger.info(f"[Client B] Holding transaction open. (Backend PID: {pid_b})")

            if pid_b != pid_1:
                logger.info(f"Client B got PID {pid_b} instead of {pid_1}. Opening Client C to occupy {pid_1}...")
                conn_c = engine.connect()
                trans_c = conn_c.begin()
                pid_c = conn_c.execute(text("SELECT pg_backend_pid()")).scalar()
                logger.info(f"[Client C] Holding transaction open. (Backend PID: {pid_c})")
                trans_b.rollback()
                trans_b = None
                logger.info("Released Client B's transaction.")

            # Transaction 2: Try to read from the temp table on Client A
            logger.info(f"Attempting to query {table_name} in Transaction 2...")
            with conn_a.begin():
                pid_2 = conn_a.execute(text("SELECT pg_backend_pid()")).scalar()
                logger.info(f"[Tx 2] Current Backend PID: {pid_2}")
                res = conn_a.execute(text(f"SELECT name FROM {table_name}")).scalar()
                logger.info(f"[Tx 2] Success! Found item: {res} (Backend PID: {pid_2})")

        except ProgrammingError as e:
            logger.error("❌ FAILED! Temporary table is missing in Transaction 2 as expected:")
            logger.error(f"  * Exception type: {type(e).__name__}")
            logger.error(f"  * Error message : {str(e.orig).strip()}")
            logger.info("Why? The backend connection with the temp table was occupied.")
            logger.info(
                "PgBouncer routed Client A's Tx 2 to a different backend connection, where temp_items does not exist."
            )
            logger.info("Implication: Temporary tables are incompatible with transaction pooling.")
        finally:
            # Clean up held transactions
            if trans_c:
                trans_c.rollback()
            if trans_b:
                trans_b.rollback()
            if conn_c:
                conn_c.close()


def test_advisory_locks_leakage():
    print_separator("TEST 2: ADVISORY LOCK LEAKAGE / CORRUPTION")

    # We will use two connections.
    # Client A will acquire an advisory lock on transaction mode.
    # We will show that even after Client A ends its transaction, the lock remains
    # active on the backend connection, but Client A's connection can no longer release it.

    direct_engine = get_direct_engine()
    bouncer_engine = get_transaction_bouncer_engine(disable_prepared=True)

    lock_id = 99999

    # Reset any existing advisory locks first by terminating backend sessions holding them
    logger.info("Resetting advisory locks on direct engine...")
    with direct_engine.connect() as conn:
        pids = conn.execute(text("SELECT DISTINCT pid FROM pg_locks WHERE locktype = 'advisory'")).fetchall()
        for row in pids:
            pid = row[0]
            logger.info(f"  * Terminating backend session PID {pid} holding stale advisory lock...")
            conn.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid})
        if pids:
            time.sleep(0.5)

    show_active_advisory_locks(direct_engine, "Initial State")

    logger.info("Opening client connections...")
    with bouncer_engine.connect() as conn_a, bouncer_engine.connect() as conn_b:
        trans_b = None
        trans_c = None
        conn_c = None
        try:
            # Tx 1: Client A acquires lock
            logger.info("Client A connecting via PgBouncer to acquire advisory lock...")
            with conn_a.begin():
                acquired = conn_a.execute(text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": lock_id}).scalar()
                pid_1 = conn_a.execute(text("SELECT pg_backend_pid()")).scalar()
                logger.info(f"[Client A - Tx 1] Try lock status = {acquired} (Backend PID: {pid_1})")

            # Tx 1 committed. Physical connection returned to PgBouncer.
            # Let's inspect locks directly on PostgreSQL.
            show_active_advisory_locks(direct_engine, "After Client A Tx 1 Commit")

            # Occupy the backend connection that has the advisory lock
            logger.info("Client B starting Tx to occupy a backend connection...")
            trans_b = conn_b.begin()
            pid_b = conn_b.execute(text("SELECT pg_backend_pid()")).scalar()
            logger.info(f"[Client B] Holding transaction open. (Backend PID: {pid_b})")

            if pid_b != pid_1:
                logger.info(f"Client B got PID {pid_b} instead of {pid_1}. Opening Client C to occupy {pid_1}...")
                conn_c = bouncer_engine.connect()
                trans_c = conn_c.begin()
                pid_c = conn_c.execute(text("SELECT pg_backend_pid()")).scalar()
                logger.info(f"[Client C] Holding transaction open. (Backend PID: {pid_c})")
                trans_b.rollback()
                trans_b = None
                logger.info("Released Client B's transaction.")

            # Tx 2: Client A tries to release the lock in a new transaction
            logger.info("[Client A] Tx 2: Attempting to unlock the advisory lock...")
            with conn_a.begin():
                current_pid = conn_a.execute(text("SELECT pg_backend_pid()")).scalar()
                logger.info(f"[Client A] Tx 2: Current Backend PID: {current_pid}")
                released = conn_a.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id}).scalar()
                logger.info(f"[Client A] Tx 2: Unlock status = {released}")

            # Let's see if the lock is actually released.
            show_active_advisory_locks(direct_engine, "After Client A Tx 2 Unlock Attempt")

        except Exception as e:
            logger.error(f"Error during advisory lock test: {e}")
        finally:
            # Clean up held transactions
            if trans_c:
                trans_c.rollback()
            if trans_b:
                trans_b.rollback()
            if conn_c:
                conn_c.close()

    # Clean up
    logger.info("Cleaning up locks on direct engine...")
    with direct_engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_unlock_all()"))

    logger.info("--- SUMMARY OF BEHAVIOR ---")
    logger.info("If Client A's Tx 2 is routed to a different physical connection (Backend PID changed),")
    logger.info("the pg_advisory_unlock() call returns FALSE or releases a lock on a different connection.")
    logger.info("The original lock remains LEAKED on the first physical connection!")
    logger.info("In AWS RDS Proxy, to prevent this exact corruption, the proxy detects advisory locks")
    logger.info("and automatically PINS the client session to the backend connection for its lifetime.")
    logger.info("This is called 'Connection Pinning' and it can quickly exhaust the RDS Proxy pool if misused.")


def main():
    print_separator("BOOTSTRAPPING DATABASE")
    init_db()

    # test_temporary_tables_failure()
    # time.sleep(2)
    test_advisory_locks_leakage()


if __name__ == "__main__":
    main()
