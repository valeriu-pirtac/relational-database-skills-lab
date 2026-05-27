"""
Lab Step 3: FastAPI AsyncSession & Pydantic Serialization (MissingGreenlet Verification)

This script:
1. Resets and seeds the database.
2. Launches the FastAPI app in a background daemon thread on port 8000.
3. Sends an HTTP request to the lazy loading route (/lazy-load-error) and catches the intentional MissingGreenlet exception.
4. Sends an HTTP request to the eager loading route (/lazy-load-fixed) and verifies clean JSON serialization.
"""

import threading
import time
from decimal import Decimal

import httpx
import uvicorn
from app.dependencies import get_session_factory, init_db
from app.models import BankAccount, User
from loguru import logger


def seed_database() -> None:
    """Seeds Alice bank account with initial balance."""
    logger.info("[Seed] Seeding initial database data...")
    session_factory = get_session_factory()

    with session_factory() as session:
        # Create Alice
        alice = User(username="alice", email="alice@bank.com")
        session.add(alice)
        session.flush()

        alice_acc = BankAccount(
            user_id=alice.id,
            account_number="ACC_ALICE",
            balance=Decimal("1000.00"),
        )
        session.add(alice_acc)
        session.commit()
    logger.success("[Seed] Seeding complete.")


def start_fastapi_server() -> None:
    """Runs the Uvicorn server in a background thread."""
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")


def test_lazy_loading_endpoint() -> None:
    """Verifies that accessing lazy relationships in async FastAPI throws MissingGreenlet."""
    logger.info("=== [API Test] Requesting /lazy-load-error (Expects MissingGreenlet failure) ===")

    try:
        response = httpx.get("http://127.0.0.1:8000/lazy-load-error", timeout=5.0)
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
    logger.info("=== [API Test] Requesting /lazy-load-fixed (Expects clean success) ===")

    try:
        response = httpx.get("http://127.0.0.1:8000/lazy-load-fixed", timeout=5.0)
        logger.info(f"API Response Status Code: {response.status_code}")

        if response.status_code == 200:
            account = response.json()
            logger.success("[Success] Loaded bank account with full nesting!")
            logger.info(f"   Account Number: {account['account_number']}")
            logger.info(f"   Balance:        ${account['balance']}")
            logger.info(f"   User Name:      {account['user']['username']}")
            logger.info(f"   User Email:     {account['user']['email']}")
        else:
            logger.error(f"[Fail] Expected 200 but got: {response.status_code}")

    except Exception as e:
        logger.error(f"HTTP request failed: {e}")


def main() -> None:
    logger.info("=============================================================")
    logger.info("LAB STEP 3: FastAPI AsyncSession & Pydantic Serialization")
    logger.info("=============================================================")

    logger.info("Initializing database...")
    init_db()
    seed_database()

    # 1. Launch FastAPI server in daemon thread
    logger.info("[Server] Spinning up FastAPI app in background thread...")
    server_thread = threading.Thread(target=start_fastapi_server, daemon=True)
    server_thread.start()

    # Wait for server to boot up
    time.sleep(2)

    # 2. Test the endpoints
    test_lazy_loading_endpoint()
    logger.info("-" * 60)
    test_eager_loading_endpoint()

    logger.info("=============================================================")
    logger.info("Lab Step 3 Complete!")
    logger.info("=============================================================")


if __name__ == "__main__":
    main()
