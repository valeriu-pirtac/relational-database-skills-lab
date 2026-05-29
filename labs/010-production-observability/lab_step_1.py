"""
Lab Step 1: Analyzing Slow Queries with pg_stat_statements

This script simulates a workload and then queries pg_stat_statements
to identify the most expensive queries.
"""

import random

from app.dependencies import get_session_factory, init_db
from app.models import EventLog
from loguru import logger
from sqlalchemy import text


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def populate_data(session):
    """Insert dummy event logs to query against."""
    logger.info("Populating database with 5000 event logs...")
    events = []
    types = ["login", "purchase", "view", "logout"]
    for _ in range(5000):
        events.append(
            EventLog(
                user_id=random.randint(1, 100), event_type=random.choice(types), duration_ms=random.uniform(10.0, 500.0)
            )
        )
    session.bulk_save_objects(events)
    session.commit()
    logger.info("Data populated.")


def generate_workload(session):
    """Run some fast and slow queries multiple times."""
    logger.info("Generating query workload...")

    # Reset pg_stat_statements stats
    session.execute(text("SELECT pg_stat_statements_reset()"))
    session.commit()

    # Query 1: Fast exact match (Indexed) - Run 50 times
    for _ in range(50):
        session.execute(
            text("SELECT id, user_id FROM event_logs WHERE id = :id"), {"id": random.randint(1, 5000)}
        ).fetchall()

    # Query 2: Slower aggregation - Run 10 times
    for _ in range(10):
        session.execute(text("SELECT event_type, AVG(duration_ms) FROM event_logs GROUP BY event_type")).fetchall()

    # Query 3: Slowest full table scan with sort - Run 5 times
    for _ in range(5):
        session.execute(text("SELECT * FROM event_logs ORDER BY created_at DESC LIMIT 100")).fetchall()


def analyze_stats(session):
    """Query pg_stat_statements to find the most expensive queries."""
    print_separator("pg_stat_statements Top Queries by Total Time")

    query = text("""
        SELECT
            query,
            calls,
            ROUND(total_exec_time::numeric, 2) as total_time_ms,
            ROUND(mean_exec_time::numeric, 2) as mean_time_ms
        FROM pg_stat_statements
        WHERE query NOT LIKE '%pg_stat%'
        ORDER BY total_exec_time DESC
        LIMIT 3;
    """)

    results = session.execute(query).fetchall()

    for row in results:
        logger.info(f"Calls: {row.calls} | Total: {row.total_time_ms}ms | Mean: {row.mean_time_ms}ms")
        logger.info(f"Query: {row.query[:100]}...")
        logger.info("-" * 40)


def main() -> None:
    """Main entry point for this lab step."""
    logger.info("Initializing database...")
    init_db()

    session_factory = get_session_factory()
    with session_factory() as session:
        populate_data(session)
        generate_workload(session)
        analyze_stats(session)

    print_separator("Lab Step 1 Complete!")


if __name__ == "__main__":
    main()
