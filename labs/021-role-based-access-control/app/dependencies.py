from loguru import logger
from sqlalchemy import create_engine, text

from app.config import get_db_uri
from app.models import Base


# The admin engine connects as the 'postgres' superuser to bootstrap the architecture
admin_engine = create_engine(get_db_uri(), echo=False)


def init_db() -> None:
    logger.info("[Database] Initializing RBAC Roles and Base Schema...")

    # 1. Bootstrap the Roles
    # We must use AUTOCOMMIT isolation level to execute DROP/CREATE ROLE commands
    with admin_engine.execution_options(isolation_level="AUTOCOMMIT").begin() as conn:
        # Idempotent cleanup using DO block to avoid errors if roles don't exist
        conn.execute(
            text("""
            DO $$
            BEGIN
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_readwrite') THEN
                    DROP OWNED BY app_readwrite CASCADE;
                    DROP ROLE app_readwrite;
                END IF;
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_readonly') THEN
                    DROP OWNED BY app_readonly CASCADE;
                    DROP ROLE app_readonly;
                END IF;
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_owner') THEN
                    DROP OWNED BY app_owner CASCADE;
                    DROP ROLE app_owner;
                END IF;
            END
            $$;
        """)
        )

        # Create the Migrator/Owner Role
        conn.execute(text("CREATE ROLE app_owner WITH LOGIN PASSWORD 'owner_pass';"))
        # Create the API Application Role
        conn.execute(text("CREATE ROLE app_readwrite WITH LOGIN PASSWORD 'rw_pass';"))
        # Create the Analytics Role
        conn.execute(text("CREATE ROLE app_readonly WITH LOGIN PASSWORD 'ro_pass';"))

        # Grant basic connection rights
        conn.execute(text("GRANT CONNECT ON DATABASE rbac TO app_owner, app_readwrite, app_readonly;"))
        conn.execute(text("GRANT USAGE ON SCHEMA public TO app_owner, app_readwrite, app_readonly;"))
        # In PG 15+, public schema doesn't grant CREATE by default. We must grant it to the migration role.
        conn.execute(text("GRANT CREATE ON SCHEMA public TO app_owner;"))

    # 2. Bootstrap the Schema
    Base.metadata.drop_all(bind=admin_engine)
    Base.metadata.create_all(bind=admin_engine)

    # 3. Establish Ownership and Initial Grants
    with admin_engine.begin() as conn:
        # Hand over table ownership to the migration role
        conn.execute(text("ALTER TABLE employees OWNER TO app_owner;"))

        # Grant DML permissions to the API role for existing tables
        conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_readwrite;"))
        conn.execute(text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_readwrite;"))

        # Grant Read-Only permissions to the Analytics role for existing tables
        conn.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_readonly;"))

    logger.info("[Database] Roles created and permissions granted.")
