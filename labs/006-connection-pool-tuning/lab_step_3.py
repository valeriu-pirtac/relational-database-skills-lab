"""
Lab Step 3: Server-Side Connection Saturation & OperationalError (Async Edition)

This script:
1. Simulates horizontal scaling of application workers (e.g., 5 microservice containers).
2. Each worker establishes its own async SQLAlchemy engine with pool_size=4.
3. Each worker concurrently opens 4 connections, attempting to acquire 20 total physical connections.
4. Captures the resulting server-side PostgreSQL OperationalError:
   "FATAL: remaining connection slots are reserved..." or "sorry, too many clients".
5. Illustrates why connection pooling must be sized globally and why PgBouncer/RDS Proxy is required.
"""

import asyncio
import threading

from app.dependencies import get_custom_engine
from loguru import logger
from sqlalchemy import text


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def simulate_worker_nodes() -> None:
    """Simulates 5 independent workers saturating the server max_connections limit (15)."""
    print_separator("SERVER-SIDE CONNECTION SATURATION BENCHMARK (ASYNC)")
    logger.warning("[App System] Simulating 5 independent worker containers scaling up...")
    logger.warning("[App System] Database server limit is set to max_connections=15.")
    logger.warning("[App System] Each worker requests pool_size=4 connections (Total: 20)...")

    errors_caught = []
    active_connections = []

    # Thread barrier to coordinate concurrent checkout
    barrier = threading.Barrier(5)

    async def async_worker(worker_id: int):
        # Create an independent async engine representing a separate app container/process
        engine = get_custom_engine(pool_size=4, max_overflow=0, pool_pre_ping=False, is_async=True)
        local_connections = []

        # Sync execution via the barrier
        barrier.wait()

        try:
            # Attempt to check out 4 connections concurrently in this worker
            for conn_id in range(4):
                conn = await engine.connect()
                # Run a light query to activate the connection
                await conn.execute(text("SELECT 1"))
                local_connections.append(conn)
                active_connections.append(conn)
                logger.info(f"  [Worker {worker_id}] Successfully opened connection #{conn_id + 1}")

            # Keep connections open momentarily to hold slots
            await asyncio.sleep(3.0)

        except Exception as e:
            err_msg = str(e)
            logger.error(f"  [Worker {worker_id} FAILURE] Connection failed at checkout!")
            logger.error(f"                         Details: {err_msg[:120]}...")
            errors_caught.append(err_msg)

        finally:
            # Clean up checked-out connections in this worker
            for c in local_connections:
                try:
                    await c.close()
                except Exception:
                    pass
            await engine.dispose()

    def run_worker_thread(worker_id: int):
        # Run the async worker inside a thread-local event loop
        asyncio.run(async_worker(worker_id))

    # Launch 5 parallel workers
    threads = []
    for i in range(5):
        t = threading.Thread(target=run_worker_thread, args=(i + 1,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    logger.info("=" * 60)
    logger.info("=== DATABASE SERVER SATURATION RESULTS ===")
    logger.info(f"Total connections safely closed: {len(active_connections)}")
    logger.info(f"Total saturation errors caught:   {len(errors_caught)}")
    logger.warning(f"Errors: {errors_caught}")

    if len(errors_caught) > 0:
        logger.success("[PASS] Successfully demonstrated server-side connection exhaustion (max_connections exceeded)!")
    else:
        logger.error("[FAIL] Did not trigger server-side saturation. Max connections might be configured too high.")
    logger.info("=" * 60)


def main() -> None:
    simulate_worker_nodes()

    logger.info("=" * 60)
    logger.info("Lab Step 3 Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
