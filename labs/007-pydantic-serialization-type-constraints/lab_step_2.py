"""
Lab Step 2: Dynamic JSONB Column Validation with Pydantic

This script:
1. Simulates API payloads targeting a Product containing a JSONB `specs` column.
2. Demonstrates how Pydantic v2 catches structural, type, and value constraint violations
   (e.g., negative dimensions, excessive warranty years) before database transaction execution.
3. Inserts a valid Product record.
4. Retrieves the Product and verifies that the raw database JSONB payload is parsed
   back into structured, type-safe Pydantic objects.
"""

import asyncio

from app.dependencies import AsyncSessionLocal, init_db
from app.models import Product
from app.schemas import ProductCreate, ProductResponse
from loguru import logger
from pydantic import ValidationError
from sqlalchemy import select


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


async def async_main() -> None:
    print_separator("STEP 2: DYNAMIC JSONB COLUMN VALIDATION WITH PYDANTIC")

    # 1. Warm up database
    logger.info("[Database] Resetting tables...")
    init_db()

    # 2. Simulate an INVALID product payload (Warranty years out of bounds, negative weight)
    invalid_payload = {
        "name": "Super-Cool Mechanical Keyboard",
        "price": 149.99,
        "specs": {
            "weight_kg": -0.85,  # Unsafe: weight must be > 0
            "warranty_years": 15,  # Unsafe: max warranty allowed is 10 years
            "dimensions": {
                "width": 35.0,
                "height": 4.0,
                "depth": -12.0,  # Unsafe: depth must be > 0
            },
            "tags": ["peripherals", "rgb"],
        },
    }

    logger.warning("[API Client] Simulating incoming invalid payload insertion...")
    try:
        # Validate using ProductCreate request schema
        validated_input = ProductCreate.model_validate(invalid_payload)
        logger.success(f"[Success] Validated successfully? (Unexpected!): {validated_input}")
    except ValidationError as e:
        logger.error("[Pydantic FAIL] Input validation failed as predicted!")
        logger.error(f"Error Count: {len(e.errors())} violations detected.")
        for err in e.errors():
            loc = " -> ".join(map(str, err["loc"]))
            logger.error(f"  [{loc}]: {err['msg']} (Input was: {err.get('input')})")

    # 3. Simulate a VALID product payload
    valid_payload = {
        "name": "Pro Ergonomic Standing Desk",
        "price": 650.00,
        "specs": {
            "weight_kg": 35.5,
            "warranty_years": 5,
            "dimensions": {
                "width": 140.0,
                "height": 75.0,
                "depth": 80.0,
            },
            "tags": ["furniture", "office", "ergonomic"],
        },
    }

    logger.info("[API Client] Simulating incoming valid payload...")
    validated_input = ProductCreate.model_validate(valid_payload)
    logger.success("[Pydantic] Validated successfully!")

    # 4. Insert into PostgreSQL JSONB column
    logger.info("[Database] Persisting validated specs to JSONB column...")
    async with AsyncSessionLocal() as session:
        new_product = Product(
            name=validated_input.name,
            price=validated_input.price,
            # Store the specs Pydantic model directly as a Python dictionary
            specs=validated_input.specs.model_dump(),
        )
        session.add(new_product)
        await session.commit()
        product_id = new_product.id
    logger.success(f"[Database] Product successfully persisted with ID: {product_id}")

    # 5. Fetch and deserialize raw JSONB back to strict Pydantic models
    print_separator("DESERIALIZATION & TYPE RECOVERY")
    logger.info("[Database] Fetching Product and JSONB payload from PostgreSQL...")
    async with AsyncSessionLocal() as session:
        query = select(Product).where(Product.id == product_id)
        result = await session.execute(query)
        db_product = result.scalar_one_or_none()

        assert db_product is not None
        logger.info(f"[Database] Loaded ORM object: {db_product}")
        logger.info(f"[Database] Raw JSONB dict loaded: {db_product.specs} (Type: {type(db_product.specs).__name__})")

        # Use Pydantic model_validate with from_attributes to automatically parse the JSONB dict
        # back into rich nested Dimensions and ProductSpecs schemas!
        product_response = ProductResponse.model_validate(db_product)

        logger.success("[Pydantic] Successfully parsed and validated raw JSONB back to strict Pydantic schemas!")
        logger.info(f"[Output Model] Weight: {product_response.specs.weight_kg}kg")
        logger.info(f"[Output Model] Width: {product_response.specs.dimensions.width}cm")
        logger.info(f"[Output Model] Warranty: {product_response.specs.warranty_years} years")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
