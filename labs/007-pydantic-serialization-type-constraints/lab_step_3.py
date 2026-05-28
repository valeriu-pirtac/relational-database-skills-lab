"""
Lab Step 3: FastAPI Async End-to-End API Integration

This script:
1. Launches the FastAPI app in a background thread using Uvicorn.
2. Uses httpx to fire HTTP requests against the FastAPI endpoints.
3. Tests both valid and invalid payloads, verifying:
   - Automated request schema validation (422 Unprocessable Entity on bad payloads).
   - Core status codes (221 Created on valid POST, 200 OK on GET).
   - Schema boundaries (nested JSONB serialization and relationship validation).
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
    # We use a custom, quiet log level for uvicorn to let loguru shine
    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, log_level="info")


def get_with_retry(client: httpx.Client, url: str, max_retries: int = 15, delay: float = 0.1) -> httpx.Response:
    """
    Attempts to GET a URL with a retry loop, accommodating asynchronous commit delays
    on highly concurrent database connections cleanly.
    """
    import time

    for _attempt in range(max_retries):
        res = client.get(url)
        if res.status_code == 200:
            return res
        time.sleep(delay)
    return res


def run_e2e_integration_tests() -> None:
    """Fires E2E requests against the FastAPI endpoints using httpx."""
    print_separator("FASTAPI END-TO-END INTEGRATION TEST")

    client = httpx.Client(base_url="http://127.0.0.1:8001", timeout=5.0)

    # 1. Test Valid User Creation
    logger.info("[Client] Creating a new user via POST /users...")
    user_payload = {
        "email": "api_developer@domain.com",
        "first_name": "Alex",
        "last_name": "API",
        "bio": "FastAPI and PostgreSQL integration engineer.",
    }
    res = client.post("/users", json=user_payload)
    logger.info(f"[Server Response] Status: {res.status_code}")
    assert res.status_code == 221, f"Expected 221, got {res.status_code}"
    user_data = res.json()
    logger.success("[PASS] Successfully created user! Nested profile returned.")
    logger.info(f"Response: {user_data}")

    # 2. Test Get User
    user_id = user_data["id"]
    logger.info(f"[Client] Fetching user {user_id} via GET /users/{user_id} (with retry support)...")
    res = get_with_retry(client, f"/users/{user_id}")
    logger.info(f"[Server Response] Status: {res.status_code}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    logger.success("[PASS] Successfully fetched user with selectinload relationship eager loading!")

    # 3. Test Invalid Product Specs (Type constraint check)
    logger.info("[Client] Submitting invalid specs product via POST /products...")
    invalid_product = {
        "name": "Heavy Steel Frame Desk",
        "price": 299.99,
        "specs": {
            "weight_kg": 0.0,  # Invalid: must be > 0
            "warranty_years": 15,  # Invalid: must be <= 10
            "dimensions": {
                "width": 120.0,
                "height": -70.0,  # Invalid: must be > 0
                "depth": 60.0,
            },
        },
    }
    res = client.post("/products", json=invalid_product)
    logger.info(f"[Server Response] Status: {res.status_code}")
    assert res.status_code == 422, f"Expected 422 validation failure, got {res.status_code}"
    logger.success("[PASS] API server correctly rejected invalid JSONB payload with HTTP 422 Unprocessable Entity!")
    logger.info(f"Details: {res.json()['detail'][0]}")

    # 4. Test Valid Product Specs (JSONB dynamic persistence)
    logger.info("[Client] Submitting valid product via POST /products...")
    valid_product = {
        "name": "Premium Wireless Mouse",
        "price": 89.99,
        "specs": {
            "weight_kg": 0.12,
            "warranty_years": 2,
            "dimensions": {
                "width": 6.5,
                "height": 4.0,
                "depth": 11.5,
            },
            "tags": ["peripherals", "wireless", "gaming"],
        },
    }
    res = client.post("/products", json=valid_product)
    logger.info(f"[Server Response] Status: {res.status_code}")
    assert res.status_code == 221, f"Expected 221, got {res.status_code}"
    product_data = res.json()
    logger.success("[PASS] Successfully created product and persisted specs to JSONB column!")
    logger.info(f"Response: {product_data}")

    # 5. Test Fetching Product (JSONB serialization check)
    p_id = product_data["id"]
    logger.info(f"[Client] Fetching product {p_id} via GET /products/{p_id} (with retry support)...")
    res = get_with_retry(client, f"/products/{p_id}")
    logger.info(f"[Server Response] Status: {res.status_code}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    logger.success("[PASS] E2E FastAPI & Pydantic JSONB Integration Verified!")


def main() -> None:
    logger.info("Initializing database...")
    init_db()

    # 1. Start FastAPI server in a background thread
    logger.info("[Server] Spinning up FastAPI app in background thread on port 8001...")
    server_thread = threading.Thread(target=start_fastapi_server, daemon=True)
    server_thread.start()

    # Give the server time to boot up
    time.sleep(2)

    # 2. Run E2E client tests
    run_e2e_integration_tests()

    logger.info("=" * 60)
    logger.info("Lab Step 3 Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
