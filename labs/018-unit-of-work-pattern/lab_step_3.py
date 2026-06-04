"""
Lab Step 3: Production-Grade Custom Unit of Work

Demonstrates how to encapsulate the SQLAlchemy session within a custom context manager class
for clean separation of concerns and automated transaction management.
"""

from decimal import Decimal

from app.dependencies import SessionLocal, init_db
from app.models import Account
from app.uow import SqlAlchemyUnitOfWork
from loguru import logger


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def transfer_funds(uow: SqlAlchemyUnitOfWork, from_name: str, to_name: str, amount: float):
    """
    A service-layer function.
    It knows absolutely nothing about the SQLAlchemy Session.
    It only knows about the Unit of Work and Repositories.
    """
    with uow:
        # 1. Fetch domain objects via repository
        sender = uow.accounts.get_by_name(from_name)
        receiver = uow.accounts.get_by_name(to_name)

        if not sender or not receiver:
            raise ValueError("Sender or receiver not found.")

        logger.info(f"[Service] Attempting transfer of ${amount} from {from_name} to {to_name}...")

        # 2. Modify objects in Python memory
        sender.balance -= Decimal(amount)
        receiver.balance += Decimal(amount)

        # 3. Automatic Lifecycle:
        # If we reach this point without exception, the uow.__exit__ block will automatically call self.commit()!
        # If an exception is raised (like IntegrityError from DB), uow.__exit__ will automatically call self.rollback()!


def main():
    init_db()

    print_separator("SEEDING INITIAL DATA VIA CUSTOM UOW")
    uow = SqlAlchemyUnitOfWork(SessionLocal)

    with uow:
        uow.accounts.add(Account(owner_name="Charlie", balance=500.0))
        uow.accounts.add(Account(owner_name="Dave", balance=100.0))
        # Context manager automatically commits here!

    logger.success("[DB] Initial accounts seeded successfully.")

    print_separator("SCENARIO A: SUCCESSFUL TRANSFER")
    transfer_funds(SqlAlchemyUnitOfWork(SessionLocal), "Charlie", "Dave", 200.0)
    logger.success("[Transfer] Completed successfully. Transaction auto-committed!")

    print_separator("SCENARIO B: FAILED TRANSFER (AUTOMATIC ROLLBACK)")
    try:
        # Charlie only has 300 left, trying to send 1000 will violate CheckConstraint
        transfer_funds(SqlAlchemyUnitOfWork(SessionLocal), "Charlie", "Dave", 1000.0)
    except Exception as e:
        logger.error(f"[Transfer Failed] Exception caught: {type(e).__name__}.")
        logger.warning(
            "[Recovery] The UoW '__exit__' block automatically rolled back the transaction AND closed the session!"
        )

    # Verify final states
    print_separator("FINAL DATABASE VERIFICATION")
    with SqlAlchemyUnitOfWork(SessionLocal) as verifier_uow:
        charlie = verifier_uow.accounts.get_by_name("Charlie")
        dave = verifier_uow.accounts.get_by_name("Dave")
        logger.success(f"Final State -> Charlie: {charlie.balance}, Dave: {dave.balance}")


if __name__ == "__main__":
    main()
