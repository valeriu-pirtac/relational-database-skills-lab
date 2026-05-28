"""
Lab Step 2: QueuePool Exhaustion and TimeoutError Diagnostics

This script:
1. Launches the FastAPI app (configured with pool_size=2, max_overflow=1, pool_timeout=2.0) in the background.
2. Fires 10 concurrent HTTP requests to the slow endpoint (/products/slow) which holds connections open for 1.0 second.
3. Captures and records the predicted QueuePoolTimeoutError exceptions on tail-end requests.
4. Demonstrates the impact of inadequate pool sizing under concurrent transactional loads.
"""

import threading
import time

import httpx
import uvicorn
from app.dependencies import init_db
from loguru import logger


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def start_fastapi_server() -> None:
    """Runs the Uvicorn server in a background thread."""
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")


def run_concurrent_slow_requests() -> None:
    """Fires 10 concurrent requests to /products/slow to force QueuePool exhaustion."""
    print_separator("QUEUEPOOL CONCURRENCY EXHAUSTION BENCHMARK")
    logger.warning("[API Client] Firing 10 concurrent requests to /products/slow (1.0s checkout delay)...")

    responses = []
    threads = []

    def make_request():
        try:
            # Hit the slow products endpoint
            response = httpx.get("http://127.0.0.1:8000/products/slow", timeout=15.0)
            responses.append((response.status_code, response.text))
        except Exception as e:
            responses.append((500, f"Request error: {e}"))

    # Spawn 10 concurrent requests
    for _ in range(10):
        t = threading.Thread(target=make_request)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Analyze outcomes
    success_count = 0
    failure_count = 0
    error_types: dict[str, int] = {}

    for status_code, body in responses:
        if status_code == 200:
            success_count += 1
        else:
            failure_count += 1
            try:
                import json

                data = json.loads(body)
                err_type = data.get("error_type", "UnknownError")
                error_types[err_type] = error_types.get(err_type, 0) + 1
            except Exception:
                error_types["HttpConnectionError"] = error_types.get("HttpConnectionError", 0) + 1

    logger.warning(
        f"[Concurrency Result] Requests completed. Successes: {success_count}/10, Failures: {failure_count}/10"
    )
    logger.info("=" * 60)
    logger.info("=== RECOVERY & FAILURE BREAKDOWN ===")
    logger.success(f"  200 OK (Succeeded): {success_count} requests")
    for err, count in error_types.items():
        logger.error(f"  500 Internal Server Error ({err}): {count} requests")
    logger.info("=" * 60)

    if failure_count > 0 and "QueuePoolTimeoutError" in error_types:
        logger.success("[PASS] Verified predicted QueuePoolTimeoutError client-side checkout failures!")
    else:
        logger.error("[FAIL] Did not capture QueuePoolTimeoutError. Check pool configuration.")


def main() -> None:
    logger.info("Initializing database...")
    init_db()

    # 1. Start FastAPI server in background thread
    logger.info("[Server] Spinning up FastAPI app in background thread...")
    server_thread = threading.Thread(target=start_fastapi_server, daemon=True)
    server_thread.start()

    # Give the server time to boot up
    time.sleep(2)

    # 2. Run the concurrent load test
    run_concurrent_slow_requests()

    logger.info("=" * 60)
    logger.info("Lab Step 2 Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
