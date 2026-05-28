"""
Lab Step 1: Decoupling Schemas & Pydantic v2 from_attributes Serialization

This script:
1. Initializes the database tables.
2. Seeds a User and UserProfile record within a transaction.
3. Retrieves the User from the database using selectinload (avoiding N+1 queries).
4. Validates and serializes the SQLAlchemy ORM model directly to UserResponse
   utilizing Pydantic v2's `model_validate` method.
"""

import asyncio

from app.dependencies import AsyncSessionLocal, init_db
from app.models import User, UserProfile
from app.schemas import UserResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import selectinload


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


async def async_main() -> None:
    print_separator("STEP 1: DECOUPLING SCHEMAS & ORM SERIALIZATION")

    # 1. Warm up the database schema
    logger.info("[Database] Seeding schema tables...")
    # init_db is a sync utility, so we run it directly
    init_db()

    # 2. Seed a test User and UserProfile within a transaction block
    logger.info("[App] Registering new user and profile...")
    async with AsyncSessionLocal() as session:
        # Create User
        user = User(email="senior_engineer@domain.com")
        session.add(user)
        await session.flush()  # Generates PK user.id for FK constraint

        # Create Profile
        profile = UserProfile(
            user_id=user.id,
            first_name="Jane",
            last_name="Dev",
            bio="Senior Database Engineer specializing in high-throughput APIs.",
        )
        session.add(profile)
        await session.commit()
    logger.success("[App] Successfully committed User and UserProfile database records.")

    # 3. Retrieve the User back from the database with eager loaded profile relationship
    logger.info("[Database] Fetching User from database (with selectinload(profile)...")
    async with AsyncSessionLocal() as session:
        query = select(User).where(User.email == "senior_engineer@domain.com").options(selectinload(User.profile))
        result = await session.execute(query)
        db_user = result.scalar_one_or_none()

        assert db_user is not None
        logger.info(f"[Database] Successfully retrieved ORM object: {db_user}")
        logger.info(f"[Database] Associated profile loaded: {db_user.profile}")

        # 4. Serialize ORM model to Pydantic Response Schema using v2 model_validate
        print_separator("Pydantic v2 model_validate (from_attributes)")
        logger.info("[Pydantic] Validating and serializing ORM model directly to UserResponse...")

        # model_validate reads from_attributes config, walking the ORM models and relationships
        # dynamically to yield a validated, typed, and structured API output.
        user_response = UserResponse.model_validate(db_user)

        logger.success("[Pydantic] Serialization complete!")
        logger.info(f"[Output Model] Pydantic object: {user_response}")
        logger.info(f"[Output JSON]  Serialized JSON: {user_response.model_dump_json(indent=2)}")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
