"""
Lab Step 2: Joins Deep-Dive: Nested Loop vs. Hash Join vs. Merge Join

This script:
1. Employs a join query between customers and orders tables.
2. Contrives individual join executions by adjusting session-level planner flags
   (enable_hashjoin, enable_mergejoin, enable_nestloop).
3. Evaluates the cost, execution time, and memory/buffer profiles of each join strategy.
"""

from app.dependencies import SessionLocal
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
    print_separator("STEP 2: JOIN STRATEGIES DEEP-DIVE (NESTED LOOP, HASH, MERGE)")

    # The join target query
    join_query = """
        SELECT c.name, o.amount, o.status
        FROM customers c
        JOIN orders o ON c.id = o.customer_id
        WHERE c.status = 'active'
    """

    with SessionLocal() as session:
        # --- TEST 1: DEFAULT OPTIMIZATION PLAN ---
        print_separator("TEST 1: DEFAULT PLAN (TYPICALLY HASH JOIN)")
        logger.info("[Planner] Letting PostgreSQL choose the optimal join strategy...")

        # Warm up
        session.execute(text(join_query))

        default_plan = run_explain_query(session, join_query)
        logger.info("\n" + default_plan)
        logger.warning("[Insight] The planner usually selects a Hash Join because both datasets are large.")
        logger.warning("          It constructs an in-memory hash table of the smaller table to achieve O(N+M) speed.")

    with SessionLocal() as session:
        # --- TEST 2: FORCED NESTED LOOP ---
        print_separator("TEST 2: FORCED NESTED LOOP JOIN")
        logger.info("[Planner] Forcing Nested Loop by disabling Hash and Merge joins...")
        session.execute(text("SET enable_hashjoin = off;"))
        session.execute(text("SET enable_mergejoin = off;"))
        session.execute(text("ANALYZE customers;"))  # Ensure stats are up to date for the planner
        session.execute(text("ANALYZE orders;"))  # Ensure stats are up to date for the planner
        session.commit()  # Ensure settings take effect

    with SessionLocal() as session:
        nested_loop_plan = run_explain_query(session, join_query)
        logger.info("\n" + nested_loop_plan)
        logger.error("[Insight] Note the massive execution time and cost increase!")
        logger.error(
            "          A Nested Loop requires searching the inner table once for EVERY row in the outer table."
        )
        logger.error("          For large datasets, this results in O(N*M) iterations and high resource usage.")

    with SessionLocal() as session:
        # Restore defaults
        session.execute(text("SET enable_hashjoin = on;"))
        session.execute(text("SET enable_mergejoin = on;"))
        session.execute(text("ANALYZE customers;"))  # Ensure stats are up to date for the planner
        session.execute(text("ANALYZE orders;"))  # Ensure stats are up to date for the planner
        session.commit()  # Ensure settings take effect

    with SessionLocal() as session:
        # --- TEST 3: FORCED MERGE JOIN ---
        print_separator("TEST 3: FORCED MERGE JOIN")
        logger.info("[Planner] Forcing Merge Join by disabling Hash and Nested Loop joins...")
        session.execute(text("SET enable_hashjoin = off;"))
        session.execute(text("SET enable_nestloop = off;"))
        session.execute(text("ANALYZE customers;"))  # Ensure stats are up to date for the planner
        session.execute(text("ANALYZE orders;"))  # Ensure stats are up to date for the planner
        session.commit()  # Ensure settings take effect

    with SessionLocal() as session:
        merge_join_plan = run_explain_query(session, join_query)
        logger.info("\n" + merge_join_plan)
        logger.success("[Insight] A Merge Join requires both inputs to be sorted by the join key.")
        logger.success("          PostgreSQL will either sort them in memory (using WorkMem) or use existing indexes.")
        logger.success("          Once sorted, it merges them in a single, efficient O(N+M) pass.")

    with SessionLocal() as session:
        # Restore all default planner settings
        session.execute(text("RESET enable_hashjoin;"))
        session.execute(text("RESET enable_mergejoin;"))
        session.execute(text("RESET enable_nestloop;"))
        session.commit()

    logger.info("=" * 60)
    logger.info("Lab Step 2 Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
