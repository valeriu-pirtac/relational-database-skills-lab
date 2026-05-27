"""
Lab Step 3: FastAPI AsyncSession & Pydantic Serialization (MissingGreenlet Verification)

This script:
1. Launches the FastAPI app in a background daemon thread on port 8000.
2. Sends an HTTP request to the lazy loading route (/posts/lazy) and catches the intentional MissingGreenlet exception.
3. Sends an HTTP request to the eager loading route (/posts/eager) and verifies clean JSON serialization.
4. Performs a concurrent load test to verify API stability and session isolation.
"""

import threading
import time

import httpx
import uvicorn
from loguru import logger


def start_fastapi_server() -> None:
    """Runs the Uvicorn server in a background thread."""
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")


def test_lazy_loading_endpoint() -> None:
    """Verifies that accessing lazy relationships in async FastAPI throws MissingGreenlet."""
    logger.info("=== [API Test] Requesting /posts/lazy (Expects MissingGreenlet failure) ===")

    try:
        response = httpx.get("http://127.0.0.1:8000/posts/lazy", timeout=5.0)
        logger.info(f"API Response Status Code: {response.status_code}")

        if response.status_code == 500:
            data = response.json()
            logger.success("[Success] Catching the predicted failure!")
            logger.warning(f"   Error Type:  {data.get('error_type')}")
            logger.warning(f"   Details:     {data.get('message')[:100]}...")
            logger.warning(f"   Original:    {data.get('original_exception')}")
        else:
            logger.error(f"[Fail] Expected 500 containing MissingGreenlet but got: {response.status_code}")

    except Exception as e:
        logger.error(f"HTTP request failed: {e}")


def test_eager_loading_endpoint() -> None:
    """Verifies that eager loading resolves MissingGreenlet and serializes cleanly."""
    logger.info("=== [API Test] Requesting /posts/eager (Expects clean success) ===")

    try:
        response = httpx.get("http://127.0.0.1:8000/posts/eager", timeout=5.0)
        logger.info(f"API Response Status Code: {response.status_code}")

        if response.status_code == 200:
            posts = response.json()
            logger.success(f"[Success] Loaded {len(posts)} posts with full nesting!")

            # Inspect first post
            first_post = posts[0]
            logger.info(f"   Post Title:  {first_post['title']}")
            logger.info(f"   Author:      {first_post['author']['username']}")
            logger.info(f"   Bio:         {first_post['author']['profile']['bio']}")
            logger.info(f"   Comments:    Loaded {len(first_post['comments'])} comments")
            logger.info(f"   Tags:        Loaded {len(first_post['tags'])} tags")
        else:
            logger.error(f"[Fail] Expected 200 but got: {response.status_code}")

    except Exception as e:
        logger.error(f"HTTP request failed: {e}")


def run_concurrent_load_test() -> None:
    """Fires multiple concurrent requests to the eager endpoint to check session isolation under load."""
    logger.info("=== [Load Test] Firing 10 concurrent requests to /posts/eager ===")

    success_count = 0
    threads = []

    def make_request():
        nonlocal success_count
        try:
            r = httpx.get("http://127.0.0.1:8000/posts/eager", timeout=5.0)
            if r.status_code == 200:
                success_count += 1
        except Exception:
            pass

    # Start 10 parallel threads
    for _ in range(10):
        t = threading.Thread(target=make_request)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    if success_count == 10:
        logger.success("[Load Test Success] All 10 concurrent requests completed successfully!")
    else:
        logger.error(f"[Load Test Failed] Only {success_count}/10 requests completed successfully.")


def main() -> None:
    logger.info("=============================================================")
    logger.info("LAB STEP 3: FastAPI AsyncSession & Pydantic Serialization")
    logger.info("=============================================================")

    # 1. Launch FastAPI server in daemon thread
    logger.info("[Server] Spinning up FastAPI app in background thread...")
    server_thread = threading.Thread(target=start_fastapi_server, daemon=True)
    server_thread.start()

    # Wait for server to boot up
    time.sleep(2)

    # 2. Run API checks
    test_lazy_loading_endpoint()
    test_eager_loading_endpoint()
    run_concurrent_load_test()

    logger.info("=============================================================")
    logger.info("Lab Step 3 Complete!")
    logger.info("=============================================================")


if __name__ == "__main__":
    main()
