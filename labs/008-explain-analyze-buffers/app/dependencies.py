import logging
import random
from datetime import datetime, timedelta

from faker import Faker
from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URL
from app.models import Base, Customer, Order


# Manage SQLAlchemy engine logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

default_sync_engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=default_sync_engine)


def init_db() -> None:
    """Drops and re-creates database tables using the default sync engine."""
    Base.metadata.drop_all(bind=default_sync_engine)
    Base.metadata.create_all(bind=default_sync_engine)
    logger.success("[Database] Base tables successfully initialized.")


def seed_database_benchmark() -> None:
    """
    Seeds the database with 20,000 Customer records and 50,000 Order records
    using bulk inserts to guarantee execution plan indexing effectiveness.
    """
    fake = Faker()
    session = SessionLocal()

    try:
        # Check if already seeded
        customer_count = session.query(Customer).count()
        if customer_count >= 20000:
            logger.info("[Seed] Database already seeded. Skipping seeding.")
            return

        logger.info("[Seed] Starting bulk database seed (20,000 customers, 50,000 orders)...")

        # 1. Seed Customers in batches
        logger.info("   [1/2] Seeding 20,000 customers...")
        statuses = ["active", "inactive", "suspended"]
        customers = []
        for i in range(20000):
            cust = Customer(
                name=fake.name(),
                # Ensure we have a predictable customer for step 1 lookups
                email=f"target_customer_{i}@performance.com" if i == 12345 else fake.unique.email(),
                status=random.choice(statuses),
                created_at=datetime.utcnow() - timedelta(days=random.randint(1, 365)),
            )
            customers.append(cust)

            if len(customers) >= 5000:
                session.add_all(customers)
                session.flush()
                customers = []
        if customers:
            session.add_all(customers)
            session.flush()

        logger.success("   [1/2] Customer seeding complete.")

        # Get customer IDs
        logger.info("   [2/2] Seeding 50,000 orders...")
        cust_ids = [c.id for c in session.query(Customer.id).all()]
        order_statuses = ["completed", "pending", "failed", "refunded"]

        orders = []
        for _ in range(50000):
            ord_date = datetime.utcnow() - timedelta(days=random.randint(1, 180))
            order = Order(
                customer_id=random.choice(cust_ids),
                amount=round(random.uniform(10.0, 1500.0), 2),
                status=random.choice(order_statuses),
                order_date=ord_date,
            )
            orders.append(order)

            if len(orders) >= 5000:
                session.add_all(orders)
                session.flush()
                orders = []
        if orders:
            session.add_all(orders)
            session.flush()

        session.commit()
        logger.success("[Seed] Seeding complete! 20,000 customers and 50,000 orders persisted successfully.")

    except Exception as e:
        session.rollback()
        logger.error(f"[Seed FAILURE] Transaction rolled back due to error: {e}")
        raise
    finally:
        session.close()
