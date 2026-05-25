import threading
import time
from decimal import Decimal

from app.dependencies import get_session_factory, init_db
from app.models import User
from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import OperationalError


def print_separator(title):
    logger.info(f"\n{'=' * 20} {title} {'=' * 20}")


def experiment_1_read_committed():
    """
    Experiment 1: Demonstrates non-repeatable reads in READ COMMITTED isolation level.
    Session B will see different values for the same row within a single transaction.
    """
    print_separator("EXPERIMENT 1: READ COMMITTED (Default)")

    session_factory = get_session_factory()
    barrier = threading.Barrier(2)  # Synchronize two threads
    event_a_updated = threading.Event()

    def session_a():
        """Session A: Creates Bob and then updates his balance."""
        with session_factory() as session:
            logger.info("[Session A] Creating Bob with balance 100.00")
            bob = User(username="bob", balance=Decimal("100.00"))
            session.add(bob)
            session.commit()

            # Wait for Session B to read the initial value
            barrier.wait()
            time.sleep(0.5)  # Give Session B time to start transaction

            logger.info("[Session A] Updating Bob's balance to 200.00 and committing")
            bob = session.query(User).filter_by(username="bob").one()
            bob.balance = Decimal("200.00")
            session.commit()
            event_a_updated.set()

    def session_b():
        """Session B: Reads Bob's balance twice in READ COMMITTED transaction."""
        # Wait for Bob to be created
        barrier.wait()
        time.sleep(0.2)

        with session_factory() as session:
            logger.info("[Session B] Starting READ COMMITTED transaction")
            session.execute(text("BEGIN TRANSACTION ISOLATION LEVEL READ COMMITTED"))

            # First read
            bob = session.query(User).filter_by(username="bob").one()
            logger.info(f"[Session B] First read: Bob's balance = {bob.balance}")
            first_balance = bob.balance

            # Wait for Session A to update
            event_a_updated.wait()
            time.sleep(0.2)

            # Second read - will see the updated value!
            bob = session.query(User).filter_by(username="bob").one()
            logger.info(f"[Session B] Second read: Bob's balance = {bob.balance}")
            second_balance = bob.balance

            session.commit()

            # Verify non-repeatable read occurred
            if first_balance != second_balance:
                logger.success(
                    f"✓ Non-repeatable read occurred! Values changed from {first_balance} to {second_balance}"
                )
            else:
                logger.warning("✗ Expected non-repeatable read but got same value")

    # Run both sessions concurrently
    thread_a = threading.Thread(target=session_a, name="Session-A")
    thread_b = threading.Thread(target=session_b, name="Session-B")

    thread_a.start()
    thread_b.start()

    thread_a.join()
    thread_b.join()

    logger.info("[Result] READ COMMITTED allows each query to see latest committed data")


def experiment_2_repeatable_read():
    """
    Experiment 2: Demonstrates snapshot isolation in REPEATABLE READ isolation level.
    Session B will see the same consistent snapshot throughout the transaction.
    """
    print_separator("EXPERIMENT 2: REPEATABLE READ")

    session_factory = get_session_factory()
    barrier = threading.Barrier(2)
    event_a_updated = threading.Event()

    def session_a():
        """Session A: Updates Bob's balance."""
        # Wait for Session B to take its snapshot
        barrier.wait()
        time.sleep(0.5)

        with session_factory() as session:
            logger.info("[Session A] Updating Bob's balance to 300.00 and committing")
            bob = session.query(User).filter_by(username="bob").one()
            bob.balance = Decimal("300.00")
            session.commit()
            event_a_updated.set()

    def session_b():
        """Session B: Reads Bob's balance twice in REPEATABLE READ transaction."""
        with session_factory() as session:
            logger.info("[Session B] Starting REPEATABLE READ transaction")
            session.execute(text("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ"))

            # First read - establishes snapshot
            bob = session.query(User).filter_by(username="bob").one()
            logger.info(f"[Session B] First read (snapshot taken): Bob's balance = {bob.balance}")
            first_balance = bob.balance

            # Signal Session A can proceed
            barrier.wait()

            # Wait for Session A to update
            event_a_updated.wait()
            time.sleep(0.2)

            # Second read - will still see the OLD value from snapshot!
            session.expire_all()  # Force SQLAlchemy to re-query
            bob = session.query(User).filter_by(username="bob").one()
            logger.info(f"[Session B] Second read (same snapshot): Bob's balance = {bob.balance}")
            second_balance = bob.balance

            session.commit()

            # Verify repeatable read - same value both times
            if first_balance == second_balance:
                logger.success(f"✓ Repeatable read confirmed! Consistent value {first_balance} throughout transaction")
            else:
                logger.warning(
                    f"✗ Expected repeatable read but values changed from {first_balance} to {second_balance}"
                )

        # Now read outside the transaction - should see the update
        with session_factory() as session:
            bob = session.query(User).filter_by(username="bob").one()
            logger.info(f"[Session B] Read after commit: Bob's balance = {bob.balance}")
            logger.info("✓ Updated value now visible outside the transaction")

    # Run both sessions concurrently
    thread_a = threading.Thread(target=session_a, name="Session-A")
    thread_b = threading.Thread(target=session_b, name="Session-B")

    thread_b.start()
    thread_a.start()

    thread_a.join()
    thread_b.join()

    logger.info("[Result] REPEATABLE READ provides transaction-level snapshot isolation")


def experiment_3_serializable():
    """
    Experiment 3: Demonstrates write skew detection in SERIALIZABLE isolation level.
    PostgreSQL will detect conflicting concurrent transactions and abort one with serialization error.
    """
    print_separator("EXPERIMENT 3: SERIALIZABLE (Write Skew Detection)")

    session_factory = get_session_factory()

    # Setup: Create Alice and Bob with initial balances
    with session_factory() as session:
        session.query(User).delete()  # Clear existing data
        session.add(User(username="alice", balance=Decimal("80.00")))
        session.add(User(username="bob", balance=Decimal("30.00")))
        session.commit()
        logger.info("[Setup] Created Alice (80.00) and Bob (30.00) - Combined: 110.00")

    barrier = threading.Barrier(2)
    event_a_updated = threading.Event()
    event_b_updated = threading.Event()
    results = {"session_a": None, "session_b": None}

    def session_a():
        """Session A: Alice attempts to withdraw $20."""
        try:
            with session_factory() as session:
                logger.info("[Session A] Starting SERIALIZABLE transaction")
                session.execute(text("BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE"))

                # Check combined balance
                total = session.query(text("SUM(balance)")).select_from(User).scalar()
                logger.info(f"[Session A] Reads combined balance: {total}")

                # Alice withdraws $20
                logger.info("[Session A] Alice withdrawing 20.00 (80.00 -> 60.00)")
                alice = session.query(User).filter_by(username="alice").one()
                alice.balance -= Decimal("20.00")
                event_a_updated.set()

                # Wait for Session B to also update
                barrier.wait()
                time.sleep(0.3)

                # Try to commit
                logger.info("[Session A] Attempting to COMMIT...")
                session.commit()
                logger.success("[Session A] ✓ COMMIT succeeded (first to commit)")
                results["session_a"] = "SUCCESS"

        except OperationalError as e:
            if "could not serialize" in str(e):
                logger.error(f"[Session A] ✗ COMMIT failed with serialization error: {e.orig}")
                results["session_a"] = "SERIALIZATION_ERROR"
            else:
                raise

    def session_b():
        """Session B: Bob attempts to withdraw $20."""
        try:
            with session_factory() as session:
                logger.info("[Session B] Starting SERIALIZABLE transaction")
                session.execute(text("BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE"))

                # Check combined balance
                total = session.query(text("SUM(balance)")).select_from(User).scalar()
                logger.info(f"[Session B] Reads combined balance: {total}")

                # Wait for Session A to update first
                event_a_updated.wait()
                time.sleep(0.1)

                # Bob withdraws $20
                logger.info("[Session B] Bob withdrawing 20.00 (30.00 -> 10.00)")
                bob = session.query(User).filter_by(username="bob").one()
                bob.balance -= Decimal("20.00")
                event_b_updated.set()

                # Synchronize with Session A before commit
                barrier.wait()
                time.sleep(0.5)  # Let Session A commit first

                # Try to commit
                logger.info("[Session B] Attempting to COMMIT...")
                session.commit()
                logger.warning("[Session B] ✓ COMMIT succeeded (unexpected)")
                results["session_b"] = "SUCCESS"

        except OperationalError as e:
            if "could not serialize" in str(e):
                logger.error("[Session B] ✗ COMMIT failed with serialization error!")
                logger.error(f"    Error: {e.orig}")
                logger.success("    ✓ Serialization conflict detected as expected!")
                results["session_b"] = "SERIALIZATION_ERROR"
            else:
                raise

    # Run both sessions concurrently
    thread_a = threading.Thread(target=session_a, name="Session-A")
    thread_b = threading.Thread(target=session_b, name="Session-B")

    thread_a.start()
    thread_b.start()

    thread_a.join()
    thread_b.join()

    # Verify final state
    with session_factory() as session:
        users = session.query(User).order_by(User.username).all()
        logger.info("[Verification] Final balances:")
        total = Decimal("0")
        for user in users:
            logger.info(f"  * {user.username}: {user.balance}")
            total += user.balance
        logger.info(f"  * Combined: {total}")

        # Check that one transaction was rolled back
        if results["session_a"] == "SUCCESS" and results["session_b"] == "SERIALIZATION_ERROR":
            logger.success("✓ SERIALIZABLE isolation prevented write skew! Session B was rolled back.")
        elif results["session_b"] == "SUCCESS" and results["session_a"] == "SERIALIZATION_ERROR":
            logger.success("✓ SERIALIZABLE isolation prevented write skew! Session A was rolled back.")
        else:
            logger.warning(f"✗ Unexpected result: Session A={results['session_a']}, Session B={results['session_b']}")

    logger.info("[Result] SERIALIZABLE detects read/write conflicts and aborts conflicting transactions")


def main():
    # 1. Reset and create tables
    logger.info("Initializing database tables...")
    init_db()

    # Run all three isolation level experiments
    experiment_1_read_committed()
    time.sleep(1)

    experiment_2_repeatable_read()
    time.sleep(1)

    experiment_3_serializable()

    print_separator("LAB STEP 2 COMPLETE")
    logger.info("All three isolation level experiments completed successfully!")
    logger.info("")
    logger.info("Summary:")
    logger.info("  • READ COMMITTED: Each query sees latest committed data (allows non-repeatable reads)")
    logger.info("  • REPEATABLE READ: Transaction sees consistent snapshot (prevents non-repeatable reads)")
    logger.info("  • SERIALIZABLE: Detects conflicts and aborts transactions (prevents all anomalies)")


if __name__ == "__main__":
    main()
