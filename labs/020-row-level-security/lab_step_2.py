"""
Lab Step 2: Transparent SQLAlchemy Integration via ContextVars and Events
"""

import contextvars

from app.dependencies import SessionLocal, default_sync_engine
from app.models import Document
from loguru import logger
from sqlalchemy import event


# Context variable to hold the tenant ID for the current async task/request
current_tenant_id = contextvars.ContextVar("current_tenant_id", default=None)


# Attach an event listener to the Engine's checkout pool.
# This fires every time a Session grabs a database connection to run queries.
@event.listens_for(default_sync_engine, "checkout")
def on_checkout(dbapi_connection, connection_record, connection_proxy):
    tenant_id = current_tenant_id.get()
    cursor = dbapi_connection.cursor()

    # Always drop privileges to the non-superuser so RLS applies
    cursor.execute("SET ROLE app_user")

    if tenant_id is not None:
        # Set the context for this specific database session
        cursor.execute(f"SET SESSION app.current_tenant = '{tenant_id}'")
    else:
        # Ensure we don't accidentally leak a previous tenant's state if the connection is reused!
        cursor.execute("RESET app.current_tenant")
    cursor.close()


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def fetch_documents():
    """
    Simulates a generic service-layer function.
    Notice how it is completely stripped of tenant-aware logic!
    It just queries the table.
    """
    with SessionLocal() as session:
        return session.query(Document).all()


def simulate_api_request(tenant_id: int | None, request_name: str):
    logger.warning(f"[{request_name}] Incoming request... ContextVar set to: {tenant_id}")

    # 1. Set the contextvar for the duration of this request simulation
    token = current_tenant_id.set(tenant_id)

    try:
        # 2. Call the generic service layer
        docs = fetch_documents()
        logger.success(f"[{request_name}] Query successful. Found {len(docs)} documents:")
        for d in docs:
            logger.info(f"   -> {d.content}")
    finally:
        # 3. Always reset contextvars when the request is done
        current_tenant_id.reset(token)


def main():
    print_separator("SIMULATING CONCURRENT API REQUESTS")
    logger.info("The service layer runs a naked 'session.query(Document).all()'.")
    logger.info("SQLAlchemy automatically injects the RLS SET statement upon connection checkout via our Event hook!")

    simulate_api_request(tenant_id=2, request_name="Request A (Stark Industries)")
    simulate_api_request(tenant_id=1, request_name="Request B (Acme Corp)")
    simulate_api_request(tenant_id=None, request_name="Request C (Unauthenticated User)")


if __name__ == "__main__":
    # Note: Assumes lab_step_1.py was run first to initialize the database schema and seed data
    main()
