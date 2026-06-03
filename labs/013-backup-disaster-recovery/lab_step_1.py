import subprocess

from app.dependencies import get_db_engine, get_session_factory, init_db
from app.models import UserAccount
from loguru import logger
from sqlalchemy import text


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def run_command(cmd: list[str]) -> str:
    """Run a shell command and return output."""
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def main():
    print_separator("STEP 1: CONTINUOUS ARCHIVING & BASE BACKUPS")

    # Verify db connection
    logger.info("Connecting to database...")
    engine = get_db_engine()
    with engine.connect() as conn:
        # Check archiving configuration
        archive_mode = conn.execute(text("SHOW archive_mode")).scalar()
        wal_level = conn.execute(text("SHOW wal_level")).scalar()
        logger.info(f"Database settings: archive_mode={archive_mode}, wal_level={wal_level}")

        if archive_mode != "on":
            logger.error("Database archive_mode is not enabled! Make sure docker compose is running.")
            return

    logger.info("Initializing database schema...")
    init_db()

    # 1. Insert initial data (before backup)
    logger.info("Inserting initial database record (Alice)...")
    session_factory = get_session_factory()
    with session_factory() as session:
        alice = UserAccount(username="alice", balance=100.0)
        session.add(alice)
        session.commit()
        logger.info(f"Persisted: {alice}")

    # 2. Force WAL archiving to verify it works
    logger.info("Forcing WAL archiving using pg_switch_wal()...")
    with engine.connect() as conn:
        # pg_switch_wal moves current WAL file to archive immediately
        conn.execute(text("SELECT pg_switch_wal()"))

    # Check if archive directory is populated
    logger.info("Checking WAL archive directory inside container...")
    archive_contents = run_command(
        [
            "docker",
            "exec",
            "postgres",
            "ls",
            "-la",
            "/var/lib/postgresql/archive",
        ]
    )
    logger.info(f"Archive directory contents:\n{archive_contents}")

    # 3. Trigger physical base backup
    logger.info("Taking physical database base backup via pg_basebackup...")
    logger.info("Running: pg_basebackup -U postgres -D /var/lib/postgresql/backups/base_backup -Fp -P")

    # We remove old backup if it exists, and run pg_basebackup
    run_command(
        [
            "docker",
            "exec",
            "postgres",
            "rm",
            "-rf",
            "/var/lib/postgresql/backups/base_backup",
        ]
    )
    run_command(
        [
            "docker",
            "exec",
            "postgres",
            "pg_basebackup",
            "-U",
            "postgres",
            "-D",
            "/var/lib/postgresql/backups/base_backup",
            "-Fp",
            "-P",
        ]
    )

    logger.info("[Success] Physical base backup completed successfully!")

    # Verify backup files exist
    backup_contents = run_command(
        [
            "docker",
            "exec",
            "postgres",
            "ls",
            "-la",
            "/var/lib/postgresql/backups/base_backup",
        ]
    )
    logger.info(f"Base backup directory contents:\n{backup_contents}")

    logger.info("=" * 60)
    logger.info("Lab Step 1 Complete!")


if __name__ == "__main__":
    main()
