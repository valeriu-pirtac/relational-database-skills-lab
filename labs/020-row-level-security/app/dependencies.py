from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import get_db_uri
from app.models import Base


default_sync_engine = create_engine(get_db_uri(), echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=default_sync_engine)


def init_db() -> None:
    logger.info("[Database] Initializing tables for Row-Level Security...")
    Base.metadata.drop_all(bind=default_sync_engine)
    Base.metadata.create_all(bind=default_sync_engine)

    # Create a non-superuser role for the application so RLS actually applies.
    # (Superusers always bypass RLS!)
    with default_sync_engine.execution_options(isolation_level="AUTOCOMMIT").begin() as conn:
        conn.execute(text("DROP ROLE IF EXISTS app_user"))
        conn.execute(text("CREATE ROLE app_user"))
        conn.execute(text("GRANT ALL ON ALL TABLES IN SCHEMA public TO app_user"))
        conn.execute(text("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO app_user"))

    with default_sync_engine.begin() as conn:
        # Enable RLS on the documents table
        conn.execute(text("ALTER TABLE documents ENABLE ROW LEVEL SECURITY"))

        # Force RLS for table owners/superusers.
        # (Crucial for this lab since we connect using the 'postgres' superuser role)
        conn.execute(text("ALTER TABLE documents FORCE ROW LEVEL SECURITY"))

        # Create the isolation policy
        # current_setting('app.current_tenant', true) returns NULL if the variable isn't set yet,
        # failing the policy and returning 0 rows safely.
        conn.execute(
            text("""
            CREATE POLICY tenant_isolation_policy ON documents
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::integer)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::integer)
        """)
        )
    logger.info("[Database] RLS Enabled and Tenant Isolation Policy created.")
