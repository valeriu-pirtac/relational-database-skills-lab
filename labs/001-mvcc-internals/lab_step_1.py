from app.dependencies import get_session_factory, init_db
from app.models import User
from loguru import logger
from sqlalchemy import text


def get_current_txid(session):
    """Utility to fetch the actual transaction ID currently assigned by PostgreSQL."""
    # Note: postgres only assigns a real transaction ID when a write happens, otherwise it returns a virtual txid.
    # We call txid_current() to force assignment of a physical transaction ID.
    result = session.execute(text("SELECT txid_current()"))
    return result.scalar()


def print_separator(title):
    logger.info(f"\n{'=' * 20} {title} {'=' * 20}")


def main():
    # 1. Reset and create tables
    logger.info("Initializing database tables...")
    init_db()

    # PHASE A: THE INSERT
    session_local = get_session_factory()
    with session_local() as session:
        print_separator("PHASE A: INSERTING ALICE")

        # Get the transaction ID for the insert transaction
        txid_insert = get_current_txid(session)
        logger.info(f"[Engine] Current Transaction ID: {txid_insert}")

        # Create new user
        alice = User(username="alice", balance=100.00)
        session.add(alice)
        session.commit()  # Commit Alice to the database

    with session_local() as session:
        # Retrieve Alice
        alice = session.query(User).filter_by(username="alice").one()

        logger.info("[Result] Physical tuple properties after INSERT:")
        logger.info(f"  * Record object: {alice}")
        logger.info(f"  * xmin (Inserting Tx ID)  : {alice.xmin} (Matches insertion Tx: {txid_insert})")
        logger.info(f"  * xmax (Deleting/Upd Tx) : {alice.xmax} (0 means active, not modified)")
        logger.info(f"  * ctid (Physical Address) : {alice.ctid} -> (Page 0, Line/Tuple index 1)")

    # PHASE B: THE UPDATE (MVCC creates a new physical version!)
    with session_local() as session:
        print_separator("PHASE B: UPDATING ALICE'S BALANCE")

        # Get current transaction ID for the update transaction
        txid_update = get_current_txid(session)
        logger.info(f"[Engine] Current Transaction ID: {txid_update}")

        alice = session.query(User).filter_by(username="alice").one()

        # Update Alice
        alice.balance = 150.00
        session.commit()

    with session_local() as session:
        # Retrieve Alice
        alice = session.query(User).filter_by(username="alice").one()

        logger.info("[Result] Physical tuple properties after UPDATE:")
        logger.info(f"  * Record object: {alice}")
        logger.info(f"  * xmin (Inserting Tx ID)  : {alice.xmin} (Updated to the update Tx ID: {txid_update})")
        logger.info(f"  * xmax (Deleting/Upd Tx) : {alice.xmax} (0 since the new version is still active)")
        logger.info(f"  * ctid (Physical Address) : {alice.ctid} -> Note it moved to a NEW slot (Page 0, index 2)!")

    # PHASE C: THE DELETE (Marking with xmax)
    with session_local() as session:
        print_separator("PHASE C: DELETING ALICE (IN TRANSACTION)")

        txid_delete = get_current_txid(session)
        logger.info(f"[Engine] Current Transaction ID: {txid_delete}")

        alice = session.query(User).filter_by(username="alice").one()

        # Before deletion, let's capture the metadata to observe later
        logger.info("[Before Delete] Row metadata before marking for deletion:")
        logger.info(f"  * xmin (Inserting Tx ID)  : {alice.xmin}")
        logger.info(f"  * xmax (Deleting/Upd Tx)  : {alice.xmax} (Still 0 - not marked for deletion yet)")
        logger.info(f"  * ctid (Physical Address) : {alice.ctid}")

        # Delete Alice but DO NOT commit yet
        session.delete(alice)
        session.flush()  # Send changes to PG, but keep transaction open

        # IMPORTANT: After DELETE + flush(), the row is invisible to THIS transaction
        # because MVCC visibility rules hide deleted rows from the deleting transaction.
        # To observe xmax being set, we need to query from a DIFFERENT concurrent transaction.

        # Open a separate concurrent session to observe the row state
        with session_local() as observer_session:
            logger.info("[Observer Transaction] Querying from a concurrent transaction...")
            res = observer_session.execute(
                text("SELECT xmin, xmax, ctid, username FROM users WHERE username = 'alice'")
            ).fetchone()

            if res:
                logger.info("[Result] Row metadata from concurrent transaction (sees uncommitted delete):")
                logger.info(f"  * xmin (Inserting Tx ID)  : {res[0]}")
                logger.info(
                    f"  * xmax (Deleting Tx ID)   : {res[1]} (Marked with Delete Tx: {txid_delete} - but not yet committed)"
                )
                logger.info(f"  * ctid (Physical Address) : {res[2]}")
                logger.info(f"  * Username                : {res[3]}")
                logger.info("  NOTE: Observer sees the row because the delete isn't committed yet!")
            else:
                logger.info("  * Observer cannot see alice (isolation prevents seeing uncommitted changes)")

        session.commit()  # Commit the deletion! Alice is now dead to the database.

    # PHASE D: AFTER COMMIT
    with session_local() as session:
        print_separator("PHASE D: POST-COMMIT VISIBILITY")

        # Try to query Alice
        alice_check = session.query(User).filter_by(username="alice").first()
        logger.info(f"[Result] Standard query for 'alice': {alice_check} (No longer visible!)")

        # In a real environment, the dead tuple still physically sits at (0, 1) and (0, 2) on disk,
        # marked as dead. In Step 3 we will learn how to measure them.


if __name__ == "__main__":
    main()
