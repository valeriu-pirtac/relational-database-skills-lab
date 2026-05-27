"""
Lab Step 2: Global Session Leakage and Concurrency Failures

This script:
1. Resets and seeds the database (Alice: $1000.00, Bob: $500.00).
2. Launches the FastAPI server in the background.
3. Fires 10 concurrent HTTP requests to the LEAKED shared-session endpoint (`/transfer/leaked`).
4. Captures and analyzes the resulting exceptions (like InvalidRequestError, PendingRollbackError).
5. Demonstrates the extreme danger of sharing SQLAlchemy sessions across async contexts.
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


def run_concurrent_leaked_transfers() -> None:
    """Fires 10 concurrent requests to the /transfer/leaked endpoint."""
    print_separator("LEAKED TRANSACTION CONCURRENCY BENCHMARK (EXPECTING ERRORS)")
    logger.warning("[API Client] Firing 10 concurrent requests to the leaked global session endpoint...")

    responses = []
    threads = []

    def make_transfer():
        try:
            payload = {"from_account": "ACC_ALICE", "to_account": "ACC_BOB", "amount": "10.00"}
            # Send post to the leaked route
            response = httpx.post("http://127.0.0.1:8000/transfer/leaked", json=payload, timeout=10.0)
            responses.append((response.status_code, response.text))
        except Exception as e:
            responses.append((500, f"Request error: {e}"))

    # Start 10 parallel threads to force database event collision
    for _ in range(10):
        t = threading.Thread(target=make_transfer)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Analyze the responses we got back
    success_count = 0
    failure_count = 0
    error_types = {}

    for status_code, body in responses:
        if status_code == 200:
            success_count += 1
        else:
            failure_count += 1
            # Parse error type if it's a JSON response from our FastAPI handler
            try:
                import json

                data = json.loads(body)
                err_type = data.get("error_type", "UnknownError")
                error_types[err_type] = error_types.get(err_type, 0) + 1
            except Exception:
                error_types["HttpConnectionError"] = error_types.get("HttpConnectionError", 0) + 1

    logger.warning(
        f"[Concurrency Result] LEAKED Transfers completed. Successes: {success_count}/10, Failures: {failure_count}/10"
    )
    logger.info("=" * 60)
    logger.info("=== ENCOUNTERED ERROR DISTRIBUTION ===")
    for err, count in error_types.items():
        logger.error(f"  {err}: {count} occurrences")
    logger.info("=" * 60)


def main() -> None:
    logger.info("Initializing database...")
    init_db()
    seed_database()

    # 1. Start FastAPI server in background thread
    logger.info("[Server] Spinning up FastAPI app in background thread...")
    server_thread = threading.Thread(target=start_fastapi_server, daemon=True)
    server_thread.start()

    # Give the server time to start up
    time.sleep(2)

    # 2. Run concurrent benchmark targeting the leaked global session endpoint
    run_concurrent_leaked_transfers()

    # 3. Fetch final bank account balances from database
    alice_bal, bob_bal = fetch_balances()
    logger.info("=== POST-LEAK BALANCE ASSESSMENT ===")
    logger.info(f"ACC_ALICE Final Balance: ${alice_bal}")
    logger.info(f"ACC_BOB Final Balance:   ${bob_bal}")

    # Under a leaked global session, transactions collide, fail, or overwrite each other.
    # Therefore, the final state is unpredictable and corrupt!
    logger.warning("[ANALYSIS] Due to session state overlaps, either connection mixing errors were raised")
    logger.warning(
        "           or silent balance corruption has occurred (expected $900.00 and $600.00, but results vary!)"
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
