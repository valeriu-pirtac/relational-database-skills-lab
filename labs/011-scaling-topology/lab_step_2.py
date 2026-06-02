import time

from app.dependencies import get_routing_session, init_db
from app.models import UserAccount
from loguru import logger
from sqlalchemy import select


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def main():
    print_separator("STEP 2: READ/WRITE ROUTING IN ACTION")

    # Reset DB tables on primary
    init_db()

    # Open RoutingSession
    logger.info("Opening a new RoutingSession context...")
    with get_routing_session() as session:
        # Action 1: Write Operation (INSERT)
        print_separator("ACTION 1: INSERTING DATA (WRITE)")
        new_account = UserAccount(username="john_doe", balance=1000.0)
        session.add(new_account)
        logger.info("[Session] Committing session. This should trigger flush to PRIMARY.")
        session.commit()

        # Since physical replication is asynchronous, we sleep briefly to ensure the update reaches the replica
        time.sleep(0.1)

        # Action 2: Read Operation (SELECT)
        print_separator("ACTION 2: QUERYING DATA (READ)")
        # Note: SQLAlchemy compiles select(UserAccount) and calls get_bind.
        # Since it is a select query, RoutingSession routes it to the REPLICA engine.
        stmt = select(UserAccount).where(UserAccount.username == "john_doe")
        logger.info("[Session] Executing SELECT statement...")
        account = session.execute(stmt).scalar_one()
        logger.info(f"[Session] Result from Replica: {account}")

        # Action 3: Write Operation (UPDATE)
        print_separator("ACTION 3: UPDATING DATA (WRITE)")
        # Modify the account
        account.balance = 1200.0
        logger.info("[Session] Committing update. This should trigger flush to PRIMARY.")
        session.commit()

        # Action 4: Read Operation (Refetching)
        print_separator("ACTION 4: RE-QUERYING UPDATED DATA (READ)")
        logger.info("[Session] Executing SELECT statement to refetch...")
        # Since physical replication is asynchronous, we sleep briefly to ensure the update reaches the replica
        time.sleep(0.1)

        # IMPORTANT: We must expire the object in the session.
        # Otherwise, SQLAlchemy will return the cached 'account' instance from its Identity Map
        # (in-memory session cache) instead of querying the Replica database!
        session.expire(account)

        account_refetched = session.execute(stmt).scalar_one()
        logger.info(f"[Session] Result from Replica after replication: {account_refetched}")

    logger.info("=" * 60)
    logger.info("Lab Step 2 Complete!")


if __name__ == "__main__":
    main()
