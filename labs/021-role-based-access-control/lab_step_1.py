"""
Lab Step 1: Testing Role Restrictions (The Principle of Least Privilege)
"""

from app.config import get_role_uri
from app.dependencies import init_db
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import sessionmaker


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def test_role(role_name: str, password: str):
    engine = create_engine(get_role_uri(role_name, password))
    local_session = sessionmaker(bind=engine)

    with local_session() as session:
        # 1. Test Read Access
        try:
            count = session.execute(text("SELECT COUNT(*) FROM employees")).scalar()
            logger.success(f"[{role_name}] READ SUCCESS: Executed SELECT statement. Count = {count}")
        except ProgrammingError as e:
            logger.error(f"[{role_name}] READ DENIED: {e.orig}")
            session.rollback()

        # 2. Test Write Access
        try:
            session.execute(text("INSERT INTO employees (name, salary) VALUES ('Test', 50000)"))
            session.commit()
            logger.success(f"[{role_name}] WRITE SUCCESS: Executed INSERT statement.")
        except ProgrammingError as e:
            logger.error(f"[{role_name}] WRITE DENIED: {e.orig}")
            session.rollback()

        # 3. Test DDL Access (ALTER TABLE)
        try:
            session.execute(text("ALTER TABLE employees ADD COLUMN department VARCHAR(50)"))
            session.commit()
            logger.success(f"[{role_name}] DDL SUCCESS: Executed ALTER TABLE statement.")
        except ProgrammingError as e:
            logger.error(f"[{role_name}] DDL DENIED: {e.orig}")
            session.rollback()


def main():
    init_db()

    print_separator("TESTING: app_readonly (Analytics / BI Tools)")
    logger.info("Expected Behavior: Can READ. Cannot WRITE. Cannot ALTER.")
    test_role("app_readonly", "ro_pass")

    print_separator("TESTING: app_readwrite (FastAPI Application)")
    logger.info("Expected Behavior: Can READ. Can WRITE. Cannot ALTER.")
    test_role("app_readwrite", "rw_pass")

    print_separator("TESTING: app_owner (Alembic Migrations)")
    logger.info("Expected Behavior: Can READ. Can WRITE. Can ALTER.")
    test_role("app_owner", "owner_pass")


if __name__ == "__main__":
    main()
