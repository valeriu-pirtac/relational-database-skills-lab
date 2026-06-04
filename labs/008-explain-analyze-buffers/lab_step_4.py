"""
Lab Step 4: Query Execution Engines & JIT Compilation

This script:
1. Resets and seeds the database with customers and orders.
2. Runs a heavy aggregation query with JIT explicitly forced ON.
3. Observes the execution plan for JIT overhead (Generation and Inlining time).
4. Disables JIT and re-runs the same query.
5. Observes the execution plan, noting that standard executor native execution can often be faster for OLTP scale workloads than the LLVM compile time.
"""

from app.dependencies import SessionLocal, init_db, seed_database_benchmark
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
    print_separator("STEP 4: QUERY EXECUTION ENGINES & JIT COMPILATION")

    # 1. Reset and seed database
    logger.info("[Database] Initializing base tables...")
    init_db()
    seed_database_benchmark()

    # We use a moderately heavy aggregation query over our dataset
    heavy_query = """
        SELECT c.status, COUNT(o.id) as order_count, SUM(o.amount) as total_revenue
        FROM customers c
        JOIN orders o ON c.id = o.customer_id
        GROUP BY c.status
    """

    print_separator("TEST 1: JIT FORCED ON")
    logger.warning("[App] Executing query with Just-In-Time (JIT) compilation forced ON...")

    with SessionLocal() as session:
        # Force JIT by lowering the cost threshold significantly
        session.execute(text("SET jit = on;"))
        session.execute(text("SET jit_above_cost = 10;"))
        session.execute(text("SET jit_inline_above_cost = 10;"))
        session.execute(text("SET jit_optimize_above_cost = 10;"))

        # Warm up the buffer cache so IO doesn't skew our CPU timing
        session.execute(text(heavy_query))

        raw_plan_jit = run_explain_query(session, heavy_query)
        logger.info(raw_plan_jit)

    logger.warning("[Observation] Look at the bottom of the EXPLAIN output for 'JIT:'.")
    logger.warning(
        "              Notice the 'Timing:' section. The planner spent significant milliseconds just compiling the LLVM code (Generation, Inlining, Optimization) before even executing the query!"
    )

    print_separator("TEST 2: JIT DISABLED (Standard Executor)")
    logger.success("[App] Executing query with JIT disabled (native execution)...")

    with SessionLocal() as session:
        session.execute(text("SET jit = off;"))

        raw_plan_no_jit = run_explain_query(session, heavy_query)
        logger.info(raw_plan_no_jit)

    logger.success("[Observation] Look at the Total Execution Time.")
    logger.success(
        "              Because this is an OLTP-scale dataset (not billions of rows), the standard PostgreSQL execution engine is often faster overall without the JIT compilation overhead."
    )
    logger.success(
        "              In production, tuning 'jit_above_cost' prevents small queries from being crippled by compilation time."
    )

    logger.info("=" * 60)
    logger.info("Lab Step 4 Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
