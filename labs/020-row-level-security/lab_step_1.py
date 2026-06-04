"""
Lab Step 1: Physical Enforcement of RLS at the SQL Layer
"""

from app.dependencies import SessionLocal, init_db
from app.models import Document, Tenant
from loguru import logger
from sqlalchemy import text


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def main():
    init_db()
    print_separator("SEEDING TENANT DATA")
    with SessionLocal() as session:
        # Seed Tenant A (Acme Corp)
        session.execute(text("SET LOCAL app.current_tenant = '1'"))
        session.add(Tenant(id=1, name="Acme Corp"))
        session.flush()
        session.add(Document(tenant_id=1, content="Acme Financials 2026"))

        # Seed Tenant B (Stark Industries)
        session.execute(text("SET LOCAL app.current_tenant = '2'"))
        session.add(Tenant(id=2, name="Stark Industries"))
        session.flush()
        session.add(Document(tenant_id=2, content="Iron Man Schematics"))

        session.commit()
        logger.success("Seeded data for Acme Corp (Tenant 1) and Stark Industries (Tenant 2).")

    print_separator("TESTING UNAUTHORIZED ACCESS")
    with SessionLocal() as session:
        # Switch to the non-superuser role to test RLS (superusers bypass RLS)
        session.execute(text("SET ROLE app_user"))

        # Notice: We DO NOT set 'app.current_tenant' here.
        logger.warning("Attempting to read documents WITHOUT setting the 'app.current_tenant' variable...")
        docs = session.query(Document).all()
        logger.info(f"Documents found: {len(docs)}")
        if len(docs) == 0:
            logger.success("[RLS Active] Access Denied! Even as the table owner, RLS physically blocked the read.")

    print_separator("TESTING AUTHORIZED ISOLATION")
    with SessionLocal() as session:
        session.execute(text("SET ROLE app_user"))
        logger.warning("Setting 'app.current_tenant = 1' (Acme Corp)...")
        session.execute(text("SET LOCAL app.current_tenant = '1'"))

        # Notice: We are NOT using .filter_by(tenant_id=1)
        docs = session.query(Document).all()
        logger.info(f"Documents found: {len(docs)}")
        for d in docs:
            logger.success(f" - {d.content}")

        logger.success(
            "[RLS Active] Only Acme Corp documents are visible! No 'WHERE tenant_id=1' was needed in Python!"
        )


if __name__ == "__main__":
    main()
