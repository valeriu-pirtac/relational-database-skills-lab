"""
Lab Step 1: Seq Scan vs. Index Scan & Buffer Diagnostics

This script:
1. Resets and seeds the database with 20,000 customers.
2. Runs a lookup query on an unindexed column, capturing the `EXPLAIN (ANALYZE, BUFFERS)` execution plan.
3. Observes the resulting Seq Scan and buffer read statistics (hard disk page accesses).
4. Creates a B-Tree index on the column.
5. Re-runs the query, observing the shift to an Index Scan and high buffer cache hits.
"""

from app.dependencies import SessionLocal, default_sync_engine, init_db, seed_database_benchmark
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
    print_separator("STEP 1: SEQ SCAN VS. INDEX SCAN & BUFFERS")

    # 1. Reset and seed database
    logger.info("[Database] Initializing base tables...")
    init_db()
    seed_database_benchmark()

    target_email = "target_customer_12345@performance.com"
    lookup_query = f"SELECT * FROM customers WHERE email = '{target_email}'"

    # 2. Execute Lookup BEFORE Index Creation (Expects Seq Scan)
    print_separator("TEST 1: UNINDEXED LOOKUP (SEQ SCAN)")
    logger.warning(f"[App] Fetching customer '{target_email}' before index creation...")

    with default_sync_engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
        conn.execute(text("DROP INDEX IF EXISTS idx_customers_email;"))

    with SessionLocal() as session:
        # We run the query once to warm up the DB, then run EXPLAIN
        session.execute(text(lookup_query))
        raw_plan = run_explain_query(session, lookup_query)
        logger.info("\n" + raw_plan)

    # Analyze key details from the plan
    logger.warning("[Observation] Note the 'Seq Scan' and 'Buffers: read=X' values.")
    logger.warning("              Because there is no index, Postgres had to read all pages from disk.")

    # 3. Create the B-Tree Index dynamically
    print_separator("DATABASE OPERATION: CREATE INDEX")
    logger.info("[Database] Creating B-Tree index 'idx_customers_email' on customers(email)...")
    with default_sync_engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
        conn.execute(text("CREATE INDEX idx_customers_email ON customers(email);"))
        conn.execute(text("ANALYZE customers;"))  # Update statistics after index creation
    logger.success("[Database] Index created successfully.")

    # 4. Execute Lookup AFTER Index Creation (Expects Index Scan / Index Only Scan)
    print_separator("TEST 2: INDEXED LOOKUP (INDEX SCAN)")
    logger.success(f"[App] Fetching customer '{target_email}' after B-Tree index creation...")

    with SessionLocal() as session:
        raw_indexed_plan = run_explain_query(session, lookup_query)
        logger.info("\n" + raw_indexed_plan)

    logger.success("[Observation] Note the shift to 'Index Scan' (or 'Index Only Scan').")
    logger.success("              Observe that 'Buffers: read' dropped to 0 and was replaced by 'shared hit'.")
    logger.success("              The query was executed in microseconds entirely from the shared buffer cache!")

    logger.info("=" * 60)
    logger.info("Lab Step 1 Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
