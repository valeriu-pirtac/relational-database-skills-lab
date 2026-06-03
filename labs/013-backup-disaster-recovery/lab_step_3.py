import os
import subprocess
import time

from app.dependencies import get_db_engine, get_session_factory
from app.models import UserAccount
from loguru import logger
from sqlalchemy import select, text


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def run_command(cmd: list[str]) -> str:
    """Run a shell command and return output."""
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def check_recovery_status() -> bool:
    """Check if the database is still in recovery mode."""
    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            in_recovery = conn.execute(text("SELECT pg_is_in_recovery()")).scalar()
            return in_recovery
    except Exception:
        # Database might be restarting or inaccessible
        return True


def main():
    print_separator("STEP 3: POINT-IN-TIME RECOVERY (PITR)")

    if not os.path.exists("recovery_target.txt"):
        logger.error("recovery_target.txt not found! Make sure you ran lab_step_2.py first.")
        return

    with open("recovery_target.txt") as f:
        recovery_target = f.read().strip()

    logger.info(f"Target recovery timestamp (T1): {recovery_target}")

    # 1. Stop the PostgreSQL database
    logger.info("Stopping PostgreSQL container to perform physical recovery...")
    run_command(["docker", "stop", "postgres"])
    logger.info("PostgreSQL container stopped.")

    # 2. Restore base backup and configure recovery target
    logger.info("Restoring files from base backup and writing recovery configurations...")
    # We use a temporary alpine container to clear data, copy backup, create recovery.signal,
    # and configure recovery_target_time in postgresql.auto.conf.
    # The UID/GID for postgres inside postgres:17-alpine is 70:70.
    restore_cmd = (
        "rm -rf /data/* && "
        "cp -rp /backups/base_backup/. /data/ && "
        "touch /data/recovery.signal && "
        f"echo \"recovery_target_time = '{recovery_target}'\" >> /data/postgresql.auto.conf && "
        "echo \"recovery_target_action = 'promote'\" >> /data/postgresql.auto.conf && "
        "chown -R 70:70 /data"
    )

    logger.info("Executing restore command via temporary alpine container...")
    run_command(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            "013-backup-disaster-recovery_pgdata_disaster:/data",
            "-v",
            "013-backup-disaster-recovery_pgbackups_disaster:/backups",
            "alpine",
            "sh",
            "-c",
            restore_cmd,
        ]
    )
    logger.info("Base backup restored and recovery.signal created.")

    # 3. Start the container back up
    logger.info("Starting PostgreSQL container to begin recovery replay...")
    run_command(["docker", "start", "postgres"])

    # 4. Wait for database to come online and finish recovery
    logger.info("Waiting for PostgreSQL to replay WALs up to target time and promote...")

    # We loop until pg_is_in_recovery() returns False
    retries = 30
    recovered = False
    for i in range(retries):
        time.sleep(2)
        try:
            in_recovery = check_recovery_status()
            if in_recovery is False:
                logger.info("[Success] PostgreSQL has finished recovery and promoted itself!")
                recovered = True
                break
            else:
                logger.info(f"Replay in progress... (pg_is_in_recovery = True) (Attempt {i + 1}/{retries})")
        except Exception:
            logger.info(f"Waiting for database port to open... (Attempt {i + 1}/{retries})")

    if not recovered:
        logger.error("Recovery timed out or failed. Check postgres container logs: docker logs postgres")
        return

    # Dispose connection pool to clear connections created during polling
    get_db_engine().dispose()

    # 5. Verify the restored data
    print_separator("VERIFYING RESTORED DATA")

    session_factory = get_session_factory()
    with session_factory() as session:
        try:
            users = session.execute(select(UserAccount).order_by(UserAccount.id)).scalars().all()
            logger.info(f"Retrieved users from restored database: {users}")

            usernames = [u.username for u in users]

            # Verify Alice (before backup) is present
            if "alice" in usernames:
                logger.info("   * Alice (pre-backup) is RESTORED.")
            else:
                logger.error("   * Alice is missing!")

            # Verify Bob (before target timestamp) is present
            if "bob" in usernames:
                logger.info("   * Bob (pre-disaster transaction) is RESTORED.")
            else:
                logger.error("   * Bob is missing!")

            # Verify Charlie (after target timestamp) is NOT present
            if "charlie" not in usernames:
                logger.info("   * Charlie (post-recovery-target transaction) is excluded as expected.")
            else:
                logger.error("   * Charlie was found! Recovery replayed too far.")

            if len(users) == 2 and "alice" in usernames and "bob" in usernames:
                print_separator("PITR SUCCESSFUL!")
                logger.info(
                    "Point-in-Time Recovery successfully restored database state to T1, preserving data up to the target and discarding the dropped table disaster."
                )
            else:
                logger.error("PITR completed but data counts/integrity did not match expectations.")

        except Exception as e:
            logger.error(f"Failed to query database after recovery: {e}")

    logger.info("=" * 60)
    logger.info("Lab Step 3 Complete!")


if __name__ == "__main__":
    main()
