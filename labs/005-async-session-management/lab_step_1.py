"""
Lab Step 1: Request-Scoped AsyncSession Lifecycle and Concurrency

This script:
1. Initializes the database and seeds two bank accounts (Alice and Bob).
2. Launches the FastAPI app in a background daemon thread on port 8000.
3. Fires 10 concurrent HTTP requests to the SAFE transfer endpoint (`/transfer/safe`).
4. Verifies that request-scoped sessions maintain transaction isolation perfectly,
   resulting in a clean and consistent final balance state.
"""

import threading
import time
from decimal import Decimal

import httpx
import uvicorn
from app.dependencies import get_session_factory, init_db
from app.models import BankAccount, User
from loguru import logger


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def seed_database() -> None:
    """Seeds Alice and Bob bank accounts with initial balances."""
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

        # Create Bob
        bob = User(username="bob", email="bob@bank.com")
        session.add(bob)
        session.flush()

        bob_acc = BankAccount(
            user_id=bob.id,
            account_number="ACC_BOB",
            balance=Decimal("500.00"),
        )
        session.add(bob_acc)

        session.commit()

    logger.success("[Seed] Database initialized and seeded: ACC_ALICE ($1000.00) & ACC_BOB ($500.00)")


def start_fastapi_server() -> None:
    """Runs the Uvicorn server in a background thread."""
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")


def fetch_balances() -> tuple[Decimal, Decimal]:
    """Fetches the current balances of Alice and Bob from the database."""
    session_factory = get_session_factory()
    with session_factory() as session:
        alice = session.query(BankAccount).filter_by(account_number="ACC_ALICE").first()
        bob = session.query(BankAccount).filter_by(account_number="ACC_BOB").first()
        return alice.balance, bob.balance


def run_concurrent_safe_transfers() -> None:
    """Fires 10 concurrent requests to the /transfer/safe endpoint."""
    print_separator("SAFE TRANSACTION CONCURRENCY BENCHMARK")
    logger.info("[API Client] Firing 10 concurrent requests transferring $10.00 from Alice to Bob...")

    success_count = 0
    failure_count = 0
    threads = []

    def make_transfer():
        nonlocal success_count, failure_count
        try:
            # We use httpx to hit the safe transfer endpoint
            payload = {"from_account": "ACC_ALICE", "to_account": "ACC_BOB", "amount": "10.00"}
            response = httpx.post("http://127.0.0.1:8000/transfer/safe", json=payload, timeout=10.0)
            if response.status_code == 200:
                success_count += 1
            else:
                failure_count += 1
                logger.error(f"Transfer failed with status {response.status_code}: {response.text}")
        except Exception as e:
            failure_count += 1
            logger.error(f"Request error: {e}")

    # Start 10 parallel threads simulating concurrent user actions
    for _ in range(10):
        t = threading.Thread(target=make_transfer)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    logger.info(
        f"[Concurrency Result] SAFE Transfers completed. Successes: {success_count}/10, Failures: {failure_count}/10"
    )


def main() -> None:
    logger.info("Initializing database...")
    init_db()
    seed_database()

    # 1. Start FastAPI server in background daemon thread
    logger.info("[Server] Spinning up FastAPI app in background thread...")
    server_thread = threading.Thread(target=start_fastapi_server, daemon=True)
    server_thread.start()

    # Give the server time to start up
    time.sleep(2)

    # 2. Run benchmark
    run_concurrent_safe_transfers()

    # 3. Verify final balances in the database
    alice_bal, bob_bal = fetch_balances()
    logger.info("=" * 60)
    logger.info("=== POST-BENCHMARK INTEGRITY CHECKS ===")
    logger.info(f"ACC_ALICE Expected: $900.00 | Actual: ${alice_bal}")
    logger.info(f"ACC_BOB Expected:   $600.00 | Actual: ${bob_bal}")

    # Alice should have lost exactly $100.00, Bob gained exactly $100.00
    if alice_bal == Decimal("900.00") and bob_bal == Decimal("600.00"):
        logger.success("[PASS] Safe request-scoped sessions kept connection contexts 100% isolated!")
    else:
        logger.error("[FAIL] Data corruption detected. Safe request-scoped sessions failed to isolate data.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
