import time

# Import dependencies to override later
from app import dependencies
from app.dependencies import get_primary_engine, get_replica_engine, get_routing_session
from app.models import UserAccount
from loguru import logger
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def is_primary_alive() -> bool:
    """Check if the primary database is active and accepting connections."""
    engine = get_primary_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            return True
    except OperationalError:
        return False


def main():
    print_separator("STEP 3: HA FAILOVER & REPLICA PROMOTION")

    # 1. Ensure the user has started the containers first
    get_replica_engine().connect().close()

    # 2. Check if primary is alive and prompt user to stop it
    if is_primary_alive():
        logger.info("Primary database (postgres_primary) is currently active.")
        logger.info("ACTION REQUIRED: Stop the primary container to simulate a failure:")
        logger.info("  docker stop postgres_primary")
        logger.info("Waiting for primary container to go offline...")

        while is_primary_alive():
            time.sleep(2)

        logger.info("[Success] Primary database is now OFFLINE!")

    print_separator("DEMONSTRATING SYSTEM STATE DURING OUTAGE")

    # 3. Try to write (expect failure)
    logger.info("Attempting a write operation (INSERT) via RoutingSession...")
    try:
        with get_routing_session() as session:
            new_user = UserAccount(username="outage_user", balance=50.0)
            session.add(new_user)
            session.commit()
        logger.error("[Failure] Write succeeded? Expected connection failure.")
    except OperationalError as e:
        logger.info("SUCCESS! Write failed as expected. Connection to Primary was refused.")
        logger.info(f"  * Exception type: {type(e).__name__}")

    # 4. Try to read (expect success)
    logger.info("Attempting a read operation (SELECT) via RoutingSession...")
    try:
        with get_routing_session() as session:
            # We fetch existing users. This query goes to Replica (port 5433).
            stmt = select(UserAccount).limit(5)
            users = session.execute(stmt).scalars().all()
            logger.info("SUCCESS! Reads are still working via the Replica!")
            logger.info(f"  * Retrieved users: {users}")
    except Exception as e:
        logger.error(f"[Failure] Read failed: {e}")

    # 5. Prompt for promotion
    print_separator("PROMOTING THE REPLICA TO PRIMARY")
    logger.info("The Primary is dead, but the Replica is active. We must promote the Replica to write-mode.")
    logger.info("ACTION REQUIRED: Run the following command in a new terminal window to promote the replica:")
    logger.info("  docker exec -it -u postgres postgres_replica pg_ctl promote -D /var/lib/postgresql/data")
    logger.info("Waiting for replica promotion...")

    replica_engine = get_replica_engine()
    is_promoted = False

    while not is_promoted:
        try:
            with replica_engine.connect() as conn:
                in_recovery = conn.execute(text("SELECT pg_is_in_recovery()")).scalar()
                if not in_recovery:
                    is_promoted = True
                    break
        except OperationalError:
            # Handle transient connectivity during transition
            pass
        time.sleep(2)

    logger.info("[Success] Replica node has been successfully promoted to Primary!")
    logger.info("  * pg_is_in_recovery() = False (Replica is now in Read-Write mode)")

    # 6. Route writes to the promoted node
    print_separator("PERFORMING WRITES ON THE PROMOTED REPLICA")
    logger.info("Simulating application-level failover (switching write engine to the promoted replica)...")

    # Override dependency function so RoutingSession targets the replica port (5433) for write queries
    dependencies.get_primary_engine = lambda: replica_engine

    try:
        with get_routing_session() as session:
            promoted_user = UserAccount(username="promoted_replica_user", balance=999.0)
            session.add(promoted_user)
            session.commit()
            logger.info("SUCCESS! Write operation completed on the promoted database (port 5433)!")

            # Read back from same engine
            stmt = select(UserAccount).where(UserAccount.username == "promoted_replica_user")
            res = session.execute(stmt).scalar_one()
            logger.info(f"  * Successfully read back record: {res}")
    except Exception as e:
        logger.error(f"[Failure] Failed to write to promoted replica: {e}")

    logger.info("=" * 60)
    logger.info("Lab Step 3 Complete!")


if __name__ == "__main__":
    main()
