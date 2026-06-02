import concurrent.futures
import time

import psycopg
from app.config import get_bouncer_admin_uri
from app.dependencies import (
    get_session_bouncer_engine,
    get_transaction_bouncer_engine,
    init_db,
)
from loguru import logger
from sqlalchemy import text


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def fetch_pgbouncer_pools(port_env_name: str) -> None:
    """Connects to the virtual 'pgbouncer' database and logs the pool state."""
    admin_uri = get_bouncer_admin_uri(port_env_name).replace("+psycopg", "")
    # Use direct psycopg connection to bypass SQLAlchemy's dialect/version checks (like version query)
    # which PgBouncer's virtual admin database does not support.
    try:
        with psycopg.connect(admin_uri, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SHOW POOLS")
                result = cur.fetchall()
                logger.info(f"--- PgBouncer Pools Status (Port: {port_env_name}) ---")
                logger.info(
                    f"{'Database':<20} | {'User':<10} | {'Client Active':<13} | "
                    f"{'Client Waiting':<14} | {'Server Active':<13} | {'Server Idle':<11}"
                )
                logger.info("-" * 90)
                found = False
                for row in result:
                    # Row columns: database, user, cl_active, cl_waiting, sv_active, sv_idle, ...
                    if row[0] == "multiplexing_db":
                        logger.info(
                            f"{row[0]:<20} | {row[1]:<10} | {row[2]:<13} | {row[3]:<14} | {row[4]:<13} | {row[5]:<11}"
                        )
                        found = True
                if not found:
                    logger.info("No active pools found for 'multiplexing_db' yet.")
                logger.info("-" * 90)
    except Exception as e:
        logger.error(f"Failed to query PgBouncer admin stats: {e}")


def worker_session(thread_id: int, hold_seconds: int):
    """
    A worker that connects via Session Pooling, executes a query, and holds the connection.
    In Session Pooling, the backend server connection is tied to this client connection
    until the client connection is closed.
    """
    engine = get_session_bouncer_engine()
    logger.info(f"[Thread {thread_id}] Attempting to connect to Session Bouncer...")
    start_time = time.time()
    try:
        with engine.connect() as conn:
            # Execute a short query to bind/activate the connection
            res = conn.execute(text("SELECT 1")).scalar()
            acquire_time = time.time() - start_time
            logger.info(f"[Thread {thread_id}] Connected! (Acquired in {acquire_time:.2f}s, result={res})")

            logger.info(f"[Thread {thread_id}] Holding connection active for {hold_seconds}s...")
            time.sleep(hold_seconds)

            logger.info(f"[Thread {thread_id}] Releasing connection.")
    except Exception as e:
        logger.error(f"[Thread {thread_id}] Error: {e}")


def worker_transaction(thread_id: int, hold_seconds: int):
    """
    A worker that connects via Transaction Pooling.
    Each query is its own transaction. In transaction pooling, PgBouncer releases
    the backend server connection back to the pool as soon as the transaction commits/rolls back.
    Even if the client stays connected and sleeps, the backend server connection is free.
    """
    engine = get_transaction_bouncer_engine(disable_prepared=True)
    logger.info(f"[Thread {thread_id}] Attempting to connect to Transaction Bouncer...")
    start_time = time.time()
    try:
        with engine.connect() as conn:
            # We open an explicit transaction block
            with conn.begin():
                res = conn.execute(text("SELECT 1")).scalar()
                acquire_time = time.time() - start_time
                logger.info(
                    f"[Thread {thread_id}] Transact 1 executed. (Acquired in {acquire_time:.2f}s, result={res})"
                )

            # The transaction has ended (committed via context manager).
            # Under transaction pooling, the physical database connection is now returned to the pool,
            # even though the client connection 'conn' is still active!
            logger.info(f"[Thread {thread_id}] Idle outside transaction. Sleeping for {hold_seconds}s...")
            time.sleep(hold_seconds)

            # Execute another query. PgBouncer will dynamically checkout a physical connection again.
            with conn.begin():
                res2 = conn.execute(text("SELECT 2")).scalar()
                logger.info(f"[Thread {thread_id}] Transact 2 executed. (result={res2})")

            logger.info(f"[Thread {thread_id}] Releasing client connection.")
    except Exception as e:
        logger.error(f"[Thread {thread_id}] Error: {e}")


def run_session_experiment():
    print_separator("TESTING SESSION POOLING (PORT 6430)")
    logger.info("PgBouncer Session pool size is capped at 2.")
    logger.info("We will spawn 5 threads concurrent clients. Each holds connection for 3s.")
    logger.info("Expectation: Threads 1 and 2 will succeed immediately. Threads 3-5 must block")
    logger.info("until the first ones release their physical connections.")

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for i in range(1, 6):
            futures.append(executor.submit(worker_session, i, 3))
            time.sleep(0.1)  # small stagger to order logs

        # Let threads acquire connections
        time.sleep(1.0)
        fetch_pgbouncer_pools("BOUNCER_SESSION_PORT")

        concurrent.futures.wait(futures)

    logger.info("Session pooling experiment complete.")


def run_transaction_experiment():
    print_separator("TESTING TRANSACTION POOLING (PORT 6431)")
    logger.info("PgBouncer Transaction pool size is capped at 2.")
    logger.info("We will spawn 5 concurrent client threads. Each runs a quick transaction,")
    logger.info("sleeps for 3 seconds outside a transaction, and runs another transaction.")
    logger.info("Expectation: All 5 threads will execute their first transaction almost immediately,")
    logger.info("because they don't hold the physical backend connection while sleeping!")

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for i in range(1, 6):
            futures.append(executor.submit(worker_transaction, i, 3))
            time.sleep(0.1)  # small stagger to order logs

        # Let threads execute first transaction and enter idle sleep state
        time.sleep(1.0)
        fetch_pgbouncer_pools("BOUNCER_TRANSACTION_PORT")

        concurrent.futures.wait(futures)

    logger.info("Transaction pooling experiment complete.")


def main():
    print_separator("BOOTSTRAPPING DATABASE")
    init_db()

    run_session_experiment()
    time.sleep(2)

    run_transaction_experiment()


if __name__ == "__main__":
    main()
