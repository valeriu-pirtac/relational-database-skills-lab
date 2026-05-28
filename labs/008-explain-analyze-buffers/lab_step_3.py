"""
Lab Step 3: Covering Indexes & The Visibility Map

This script:
1. Runs a query selecting id and status via the primary key index, observing the Index Scan (which fetches from both the index and the heap table).
2. Creates a Covering Index using the `INCLUDE` clause: `CREATE INDEX idx_customers_covering ON customers(id) INCLUDE (status)`.
3. Runs the query again, observing the shift to an `Index Only Scan` with `Heap Fetches: 0`.
4. Performs updates on the target range to dirty the heap pages in the Visibility Map.
5. Observes that the `Index Only Scan` is forced to do `Heap Fetches: 1` to check transaction visibility.
6. Runs a `VACUUM` on the table to rebuild the Visibility Map.
7. Re-runs the query and verifies that `Heap Fetches` returns to `0`.
"""

from app.dependencies import SessionLocal, default_sync_engine
from loguru import logger
from sqlalchemy import text


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def run_explain_query(session, query_str: str) -> str:
    """Executes a query prefixed with EXPLAIN (ANALYZE, BUFFERS) and returns the formatted plan."""
    explain_query = text(f"EXPLAIN (ANALYZE, BUFFERS) {query_str}")
    result = session.execute(explain_query)
    plan_lines = [row[0] for row in result]
    return "\n".join(plan_lines)


def main() -> None:
    print_separator("STEP 3: COVERING INDEXES & THE VISIBILITY MAP")

    target_id = 12345
    query_str = f"SELECT id, status FROM customers WHERE id = {target_id}"

    # Run an initial VACUUM and drop existing index to ensure idempotency and clean Visibility Map
    logger.info("[Database] Dropping existing covering index and running initial VACUUM...")
    with default_sync_engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
        conn.execute(text("DROP INDEX IF EXISTS idx_customers_covering;"))
        conn.execute(text("VACUUM customers;"))
        conn.execute(text("ANALYZE customers;"))
    logger.success("[Database] Initial setup and VACUUM complete.")

    # --- TEST 1: STANDARD INDEX SCAN (HEAP FETCH REQ) ---
    print_separator("TEST 1: INDEX SCAN")
    logger.info(f"[App] Fetching id and status for customer {target_id}...")

    with SessionLocal() as session:
        with session.begin():
            # Warm up
            session.execute(text(query_str))
            raw_plan = run_explain_query(session, query_str)
            logger.info("\n" + raw_plan)

    logger.warning("[Observation] Standard 'Index Scan' on primary key index.")
    logger.warning(
        "              PostgreSQL read the index to find the row location, then fetched the 'status' from the heap (table block)."
    )

    # --- 2. CREATE COVERING INDEX ---
    print_separator("DATABASE OPERATION: CREATE COVERING INDEX")
    logger.info("[Database] Creating covering index 'idx_customers_covering' with INCLUDE (status)...")
    with default_sync_engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
        conn.execute(text("DROP INDEX IF EXISTS idx_customers_covering;"))
        conn.execute(text("CREATE INDEX idx_customers_covering ON customers(id) INCLUDE (status);"))
        conn.execute(text("ANALYZE customers;"))
    logger.success("[Database] Covering index created successfully.")

    # --- TEST 2: INDEX ONLY SCAN (HEAP FETCHES: 0) ---
    print_separator("TEST 2: INDEX ONLY SCAN (CLEAN PAGES)")
    logger.success(f"[App] Fetching customer {target_id} using covering index...")

    with SessionLocal() as session:
        with session.begin():
            raw_covering_plan = run_explain_query(session, query_str)
            logger.info("\n" + raw_covering_plan)

    logger.success("[Observation] Shifted to 'Index Only Scan'!")
    logger.success(
        "              Note 'Heap Fetches: 0'. Because the table pages are marked clean in the Visibility Map,"
    )
    logger.success(
        "              Postgres returned the 'status' directly from the index without ever touching the heap!"
    )

    # --- 3. DIRTY THE VISIBILITY MAP ---
    print_separator("DATABASE OPERATION: DIRTY HEAP PAGES")
    logger.warning(f"[App] Performing bulk update around customer {target_id} to dirty the heap pages...")
    with SessionLocal() as session:
        with session.begin():
            session.execute(
                text(
                    f"UPDATE customers SET status = 'active' WHERE id BETWEEN {target_id - 500} AND {target_id + 500};"
                )
            )
    logger.warning("[Database] Target heap range modified. Visibility Map markings for these pages are now cleared.")

    # --- TEST 3: INDEX ONLY SCAN (HEAP FETCHES > 0) ---
    print_separator("TEST 3: INDEX ONLY SCAN (DIRTY PAGES)")
    logger.warning(f"[App] Re-querying customer {target_id} on dirty pages...")

    with SessionLocal() as session:
        with session.begin():
            raw_dirty_plan = run_explain_query(session, query_str)
            logger.info("\n" + raw_dirty_plan)

    logger.error("[Observation] Still an 'Index Only Scan', but 'Heap Fetches: 1' (or > 0) is now present!")
    logger.error("              Because the page is dirty, Postgres cannot trust the index visibility state")
    logger.error("              and is forced to fetch the heap row block to verify transaction visibility (ACID).")

    # --- 4. EXECUTE VACUUM ---
    print_separator("DATABASE OPERATION: VACUUM (REBUILD VISIBILITY MAP)")
    logger.info("[Database] Running VACUUM on customers table...")
    with default_sync_engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
        conn.execute(text("VACUUM customers;"))
    logger.success("[Database] Vacuum complete. Visibility Map successfully rebuilt and pages marked clean.")

    # --- TEST 4: INDEX ONLY SCAN (RESTORED HEAP FETCHES: 0) ---
    print_separator("TEST 4: RESTORED INDEX ONLY SCAN (HEALED)")
    logger.success(f"[App] Re-querying customer {target_id} after VACUUM...")

    with SessionLocal() as session:
        with session.begin():
            raw_healed_plan = run_explain_query(session, query_str)
            logger.info("\n" + raw_healed_plan)

    logger.success("[Observation] 'Heap Fetches' returned cleanly to 0!")
    logger.success("              The covering index-only scan is restored to peak execution efficiency.")

    logger.info("=" * 60)
    logger.info("Lab Step 3 Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
