"""
Lab Step 1: The Identity Map & State Tracking
"""

from app.dependencies import SessionLocal, init_db
from app.models import Account
from loguru import logger


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def main():
    init_db()

    print_separator("PHASE 1: TRANSIENT -> PENDING -> PERSISTENT")

    with SessionLocal() as session:
        # 1. Transient
        acc = Account(owner_name="Alice", balance=100.0)
        logger.info(f"[State] Created Account object. id={acc.id}. Is it in session? {acc in session}")

        # 2. Pending
        session.add(acc)
        logger.info("[State] session.add(acc) called.")
        logger.info(f"[Identity Map] session.new contains acc? {acc in session.new}")
        logger.info(f"[Identity Map] session.dirty contains acc? {acc in session.dirty}")

        # 3. Persistent
        logger.warning(">>> Emitting session.flush() <<<")
        session.flush()
        logger.info(f"[State] After flush, acc.id is now populated: id={acc.id}")
        logger.info(f"[Identity Map] session.new contains acc? {acc in session.new} (It moved out of new!)")

        print_separator("PHASE 2: PERSISTENT -> DIRTY")

        # 4. Dirty
        acc.balance = 200.0
        logger.info(f"[State] Modified acc.balance to {acc.balance}.")
        logger.info(f"[Identity Map] session.dirty contains acc? {acc in session.dirty}")

        logger.warning(">>> Emitting session.flush() <<<")
        session.flush()
        logger.info(f"[Identity Map] session.dirty contains acc? {acc in session.dirty} (It moved out of dirty!)")

        print_separator("PHASE 3: ROLLBACK")
        logger.warning(">>> Emitting session.rollback() instead of commit! <<<")
        session.rollback()

    # Outside the session block, let's verify if the database actually saved Alice.
    with SessionLocal() as session:
        count = session.query(Account).count()
        logger.success(f"[Verification] Total accounts in database after rollback: {count}")
        logger.success("Because we rolled back instead of committing, the flushes were undone!")


if __name__ == "__main__":
    main()
