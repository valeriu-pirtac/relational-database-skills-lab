"""
Lab Step 1: Range Partitioning & Pruning
"""

from datetime import datetime

from app.dependencies import SessionLocal, init_db
from app.models import SensorData
from loguru import logger
from sqlalchemy import text


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def run_explain(session, query_str: str) -> str:
    explain_query = text(f"EXPLAIN {query_str}")
    result = session.execute(explain_query)
    return "\n".join([row[0] for row in result])


def main():
    init_db()

    print_separator("SEEDING PARTITIONED DATA")
    with SessionLocal() as session:
        session.add(SensorData(id=1, timestamp=datetime(2023, 1, 15), device_id="D1", temperature=22.5))
        session.add(SensorData(id=2, timestamp=datetime(2023, 2, 10), device_id="D2", temperature=23.1))
        session.add(SensorData(id=3, timestamp=datetime(2023, 3, 5), device_id="D1", temperature=21.8))
        session.commit()
        logger.success("[Database] 3 rows inserted successfully into the parent 'sensor_data' table.")

        print_separator("TESTING PARTITION PRUNING")
        logger.warning("[App] Querying the parent table for February data only...")

        query = "SELECT * FROM sensor_data WHERE timestamp >= '2023-02-01' AND timestamp < '2023-03-01'"

        # Execute actual query to prove data exists
        records = session.execute(text(query)).fetchall()
        logger.info(f"[Result] Found {len(records)} records for February.")

        # Examine the execution plan
        logger.warning("[Diagnostics] Running EXPLAIN to verify Partition Pruning...")
        plan = run_explain(session, query)
        logger.info(f"\n{plan}")

        logger.success("[Observation] Notice the query plan only lists a Seq Scan on 'sensor_data_feb'!")
        logger.success(
            "[Observation] PostgreSQL completely pruned (ignored) the Jan and Mar partitions, saving massive IO."
        )


if __name__ == "__main__":
    main()
