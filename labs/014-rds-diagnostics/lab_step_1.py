import time

from app.dependencies import get_db_engine
from loguru import logger
from sqlalchemy import text


def sample_active_sessions(conn) -> list[dict]:
    """Query pg_stat_activity to find active (non-idle) sessions."""
    sql = text(
        """
        SELECT
            pid,
            query,
            state,
            wait_event_type,
            wait_event
        FROM pg_stat_activity
        WHERE state = 'active'
          AND query NOT LIKE '%pg_stat_activity%'
          AND backend_type = 'client backend';
        """
    )
    result = conn.execute(sql)
    return [dict(row._mapping) for row in result]


def main():
    logger.info("Starting local AWS Performance Insights simulator...")
    logger.info("This script samples pg_stat_activity and prints Active Session metrics.")
    logger.info("Keep this running and open another terminal to run workloads.")

    engine = get_db_engine()

    with engine.connect() as conn:
        # Verify we can connect
        conn.execute(text("SELECT 1"))

    logger.info("Starting polling loop (sampling once every 500ms)...")
    logger.info("Press Ctrl+C to stop.")

    samples = []
    sample_interval = 0.5

    try:
        while True:
            t_start = time.time()
            with engine.connect() as conn:
                active = sample_active_sessions(conn)

            samples.append(active)
            if len(samples) > 20:  # Keep a rolling window of 10 seconds (20 samples)
                samples.pop(0)

            # Calculate rolling AAS (Average Active Sessions)
            total_active_sessions = sum(len(s) for s in samples)
            aas = total_active_sessions / len(samples)

            # Flatten rolling samples to count wait event types and queries
            wait_events = {}
            queries = {}
            for s in samples:
                for session in s:
                    we_type = session.get("wait_event_type") or "CPU/Running"
                    wait_events[we_type] = wait_events.get(we_type, 0) + 1

                    # Normalize query name for grouping
                    q_text = session.get("query", "")[:50].strip()
                    queries[q_text] = queries.get(q_text, 0) + 1

            # Normalize counts by number of samples to get average active sessions per category
            aas_by_event = {k: v / len(samples) for k, v in wait_events.items()}
            aas_by_query = {k: v / len(samples) for k, v in queries.items()}

            # Print status update
            print("\033[H\033[J", end="")  # Clear screen terminal code
            print("=== AWS Performance Insights Simulator (Rolling 10s Window) ===")
            print(f"Total Average Active Sessions (AAS): {aas:.2f}")
            print("AAS > 1.0 indicates database load exceeds single-core capacity.")
            print("--- AAS by Wait Event Type ---")
            for we, val in sorted(aas_by_event.items(), key=lambda x: x[1], reverse=True):
                bar = "█" * int(val * 10)
                print(f"  {we:<15} : {val:.2f} {bar}")

            print("--- AAS by Top Queries ---")
            for q, val in sorted(aas_by_query.items(), key=lambda x: x[1], reverse=True):
                bar = "█" * int(val * 10)
                print(f"  {q:<45} : {val:.2f} {bar}")

            t_end = time.time()
            elapsed = t_end - t_start
            sleep_time = max(0.01, sample_interval - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("Collector stopped.")


if __name__ == "__main__":
    main()
