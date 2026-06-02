import time

from app.dependencies import get_transaction_bouncer_engine, init_db
from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def test_prepared_statements():
    print_separator("TEST 1: PREPARED STATEMENT CRASH & REMEDIAL CONFIGURATION")

    # 1. Test with prepared statements ENABLED (disable_prepared=False)
    # We use psycopg 3. By default, psycopg 3 automatically prepares statements
    # that are executed multiple times (prepare_threshold defaults to 5).
    logger.info("Connecting to Transaction Bouncer with PREPARED STATEMENTS ENABLED...")
    engine_with_prepared = get_transaction_bouncer_engine(disable_prepared=False)

    logger.info("Executing a parameterized query multiple times to trigger statement preparation...")
    try:
        with engine_with_prepared.connect() as conn:
            for i in range(1, 10):
                # Execute query with parameter
                # The 6th execution will trigger psycopg to prepare the statement on the server.
                # In PgBouncer transaction mode, the 6th statement prepare and 7th statement execute
                # might be sent to different physical PostgreSQL backend connections.
                with conn.begin():
                    pid = conn.execute(text("SELECT pg_backend_pid()")).scalar()
                    res = conn.execute(text("SELECT :val FROM pg_database LIMIT 1"), {"val": i}).scalar()
                    logger.info(f"  * Execution {i} (PID: {pid}): Success (returned {res})")
                time.sleep(0.1)  # Stagger to allow PgBouncer to rotate connections in between
    except (OperationalError, DBAPIError) as e:
        logger.error("❌ CRASHED! Prepared statement failed under Transaction Pooling as expected:")
        logger.error(f"  * Exception type: {type(e).__name__}")
        logger.error(f"  * Error message : {str(e.orig).strip()}")
        logger.info("This happens because the statement was prepared on one physical connection")
        logger.info("but executed on a different physical connection where it does not exist.")

    time.sleep(1)

    # 2. Test with prepared statements DISABLED (disable_prepared=True)
    logger.info("Connecting to Transaction Bouncer with PREPARED STATEMENTS DISABLED...")
    logger.info("(Passing prepare_threshold=None to connect_args)")

    engine_without_prepared = get_transaction_bouncer_engine(disable_prepared=True)

    try:
        with engine_without_prepared.connect() as conn:
            for i in range(1, 10):
                with conn.begin():
                    res = conn.execute(text("SELECT :val FROM pg_database LIMIT 1"), {"val": i}).scalar()
                    logger.info(f"  * Execution {i}: Success (returned {res})")
                time.sleep(0.1)  # Stagger
        logger.info("✅ SUCCESS! Disabling prepared statements allowed all queries to succeed.")
    except Exception as e:
        logger.error(f"❌ Unexpected failure with prepared statements disabled: {e}")


def test_session_leakage():
    print_separator("TEST 2: SESSION STATE LEAKAGE VS TRANSACTION-LOCAL STATE")

    engine = get_transaction_bouncer_engine(disable_prepared=True)

    logger.info("1. Demonstrating Session Leakage via 'SET myapp.user_id'...")
    try:
        # Client A sets custom variable to 'tokyo' in a transaction block
        with engine.connect() as conn_a:
            with conn_a.begin():
                conn_a.execute(text("SET myapp.user_id = 'tokyo'"))
                pid_a = conn_a.execute(text("SELECT pg_backend_pid()")).scalar()
                logger.info(f"[Client A] Set myapp.user_id = 'tokyo' (Backend PID: {pid_a})")

        # Under transaction pooling, Client A stays connected but is idle. Now Client B queries.
        with engine.connect() as conn_b:
            for attempt in range(1, 10):
                with conn_b.begin():
                    pid_b = conn_b.execute(text("SELECT pg_backend_pid()")).scalar()
                    val = conn_b.execute(text("SELECT current_setting('myapp.user_id', true)")).scalar()
                    logger.info(f"[Client B] Attempt {attempt} (PID: {pid_b}) myapp.user_id: {val}")
                time.sleep(0.1)

        logger.info("Notice that Client B occasionally gets 'tokyo' (leakage!) depending")
        logger.info("on which physical connection it is routed to by PgBouncer.")
    except Exception as e:
        logger.error(f"Error during session leakage demonstration: {e}")
    # finally:
    #     stop_event.set()
    #     t.join()

    time.sleep(1)

    # Start interference worker again for the second part
    # stop_event = threading.Event()
    # t = threading.Thread(target=interference_worker, daemon=True)
    # t.start()

    logger.info("2. Preventing Leakage using 'SET LOCAL myapp.user_id' (Transaction-local)...")
    logger.info("SET LOCAL applies the setting ONLY for the duration of the transaction block.")
    try:
        with engine.connect() as conn_a:
            with conn_a.begin():
                conn_a.execute(text("SET LOCAL myapp.user_id = 'london'"))
                pid_a = conn_a.execute(text("SELECT pg_backend_pid()")).scalar()
                logger.info(f"[Client A] Set LOCAL myapp.user_id = 'london' (Backend PID: {pid_a})")
                # Show inside Client A's transaction that it is set
                val_inside = conn_a.execute(text("SELECT current_setting('myapp.user_id', true)")).scalar()
                logger.info(f"[Client A] (Inside transaction) myapp.user_id: {val_inside}")

        # Transaction committed. Now Client B queries.
        with engine.connect() as conn_b:
            for attempt in range(1, 10):
                with conn_b.begin():
                    pid_b = conn_b.execute(text("SELECT pg_backend_pid()")).scalar()
                    val = conn_b.execute(text("SELECT current_setting('myapp.user_id', true)")).scalar()
                    logger.info(f"[Client B] Attempt {attempt} (PID: {pid_b}) myapp.user_id: {val}")
                time.sleep(0.1)

        logger.info(
            "✅ SUCCESS! Client B always sees the default database state (keeps previous leak 'tokyo', NOT 'london'),"
        )
        logger.info("because 'SET LOCAL' was automatically cleaned up when Client A's transaction ended.")
    except Exception as e:
        logger.error(f"Error during SET LOCAL demonstration: {e}")
    # finally:
    #     stop_event.set()
    #     t.join()


def main():
    print_separator("BOOTSTRAPPING DATABASE")
    init_db()

    test_prepared_statements()
    print_separator("TEST 1 COMPLETE")
    time.sleep(2)

    test_session_leakage()
    print_separator("TEST 2 COMPLETE")


if __name__ == "__main__":
    main()
