"""
Lab Step 2: Atomic Commits & Rollback Recovery
"""

from decimal import Decimal

from app.dependencies import SessionLocal, init_db
from app.models import Account
from loguru import logger
from sqlalchemy.exc import IntegrityError


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def seed_accounts():
    with SessionLocal() as session:
        session.add(Account(owner_name="Alice", balance=100.0))
        session.add(Account(owner_name="Bob", balance=50.0))
        session.commit()


def main():
    init_db()
    seed_accounts()

    print_separator("ATOMIC TRANSFER SIMULATION")

    with SessionLocal() as session:
        alice = session.query(Account).filter_by(owner_name="Alice").one()
        bob = session.query(Account).filter_by(owner_name="Bob").one()

        logger.info(f"[State Before] Alice Balance: {alice.balance}")
        logger.info(f"[State Before] Bob Balance: {bob.balance}")

        logger.warning("[Action] Attempting to transfer $1,000 from Alice to Bob...")

        # Business logic inside the UoW
        alice.balance -= Decimal("1000.0")
        bob.balance += Decimal("1000.0")

        logger.info(f"[Identity Map] In Python memory -> Alice: {alice.balance}, Bob: {bob.balance}")

        try:
            logger.warning(">>> Emitting session.commit() <<<")
            session.commit()
        except IntegrityError:
            logger.error(
                "[Database Error] Commit failed! CheckConstraint violated: Alice cannot have a negative balance."
            )

            logger.warning(">>> Emitting session.rollback() to recover <<<")
            session.rollback()

            logger.success("[Recovery] Rollback complete. Inspecting Python objects...")
            logger.success(f"[State After Rollback] Alice Balance: {alice.balance} (Reverted!)")
            logger.success(f"[State After Rollback] Bob Balance: {bob.balance} (Reverted!)")

    # Verify database state
    with SessionLocal() as session:
        alice_db = session.query(Account).filter_by(owner_name="Alice").one()
        bob_db = session.query(Account).filter_by(owner_name="Bob").one()
        logger.success(f"[Verification DB] Database Alice Balance: {alice_db.balance}")
        logger.success(f"[Verification DB] Database Bob Balance: {bob_db.balance}")


if __name__ == "__main__":
    main()
