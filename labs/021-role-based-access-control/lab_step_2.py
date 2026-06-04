"""
Lab Step 2: The Default Privileges Trap
"""

from app.config import get_role_uri
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import sessionmaker


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def main():
    # Connect as app_owner to simulate a new Alembic Migration running
    owner_engine = create_engine(get_role_uri("app_owner", "owner_pass"))

    print_separator("SCENARIO: RUNNING A NEW MIGRATION")
    with owner_engine.begin() as conn:
        logger.warning("[app_owner] Creating a brand new table called 'departments'...")
        conn.execute(text("DROP TABLE IF EXISTS departments;"))
        conn.execute(text("CREATE TABLE departments (id SERIAL PRIMARY KEY, name VARCHAR(50));"))
        conn.execute(text("INSERT INTO departments (name) VALUES ('Engineering');"))
        logger.success("[app_owner] Table 'departments' created and seeded successfully.")

    print_separator("THE TRAP: APPLICATION ACCESS TO THE NEW TABLE")
    # Connect as the application API
    api_engine = create_engine(get_role_uri("app_readwrite", "rw_pass"))
    api_session = sessionmaker(bind=api_engine)

    with api_session() as session:
        try:
            logger.warning("[app_readwrite] API attempting to read from the newly created 'departments' table...")
            session.execute(text("SELECT * FROM departments")).fetchall()
        except ProgrammingError as e:
            logger.error(f"[app_readwrite] ACCESS DENIED! {e.orig}")
            session.rollback()
            logger.info(
                "EXPLANATION: In PostgreSQL, creating a table does NOT automatically grant permissions to it. "
                "Even though we ran 'GRANT SELECT ON ALL TABLES' earlier, it only applied to tables that existed *at that moment*."
            )

    print_separator("THE SOLUTION: ALTER DEFAULT PRIVILEGES")
    with owner_engine.begin() as conn:
        logger.warning("[app_owner] Configuring Default Privileges for future tables...")
        # Note: We must specify "FOR ROLE app_owner" because app_owner is the one who will be creating the tables.
        conn.execute(
            text("""
            ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA public
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_readwrite;
        """)
        )
        conn.execute(
            text("""
            ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA public
            GRANT USAGE, SELECT ON SEQUENCES TO app_readwrite;
        """)
        )
        logger.success("[app_owner] Default Privileges configured.")

        logger.warning("[app_owner] Creating another brand new table called 'locations'...")
        conn.execute(text("DROP TABLE IF EXISTS locations;"))
        conn.execute(text("CREATE TABLE locations (id SERIAL PRIMARY KEY, city VARCHAR(50));"))
        conn.execute(text("INSERT INTO locations (city) VALUES ('New York');"))

    print_separator("TESTING THE FIX")
    with api_session() as session:
        try:
            logger.warning("[app_readwrite] API attempting to read from 'locations'...")
            count = session.execute(text("SELECT COUNT(*) FROM locations")).scalar()
            logger.success(f"[app_readwrite] ACCESS GRANTED! Found {count} locations. Default Privileges worked!")
        except Exception as e:
            logger.error(f"Failed: {e}")


if __name__ == "__main__":
    # Note: Assumes lab_step_1 was run first to initialize the database schema
    main()
