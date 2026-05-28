import asyncio
from collections.abc import AsyncGenerator

from fastapi import Depends, FastAPI, status
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import TimeoutError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dependencies import get_custom_engine
from app.models import Product


app = FastAPI(
    title="SQLAlchemy Connection Pool Tuning Lab API",
    description="Exposes endpoints demonstrating connection checkout cycles, QueuePool limits, and pool exhaustion.",
)

# Custom restricted async engine representing a microservice under tight connection constraints
restricted_engine = get_custom_engine(
    pool_size=2,  # Base pool size
    max_overflow=1,  # Max overflow connections
    pool_timeout=2.0,  # Wait for 2 seconds before throwing TimeoutError
    is_async=True,
)
RestrictedSessionLocal = async_sessionmaker(
    bind=restricted_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_restricted_db() -> AsyncGenerator[AsyncSession]:
    """Request-scoped dependency yielding async session from a restricted pool."""
    async with RestrictedSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()


@app.exception_handler(TimeoutError)
async def pool_timeout_exception_handler(request, exc: TimeoutError):
    """
    Catch QueuePool TimeoutError and return a highly detailed 500 error,
    explaining exactly why the client-side connection pool was exhausted.
    """
    error_detail = (
        "SQLAlchemy QueuePool TimeoutError! All pool connections (pool_size=2) "
        "and overflow slots (max_overflow=1) were held active, and the client "
        "timed out waiting for a connection after 2.0 seconds. "
        "Under high concurrency or slow queries, you must scale pool_size/max_overflow "
        "or implement a connection proxy like PgBouncer."
    )
    logger.error(f"[FastAPI Failure] Connection pool exhausted: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error_type": "QueuePoolTimeoutError", "message": error_detail, "original_exception": str(exc)},
    )


@app.get("/products/fast")
async def get_products_fast(db: AsyncSession = Depends(get_restricted_db)):  # noqa: B008
    """
    Healthy endpoint: queries products and returns immediately.
    Connections are checked out and in so fast that exhaustion is rare.
    """
    logger.info("[FastAPI Request] /products/fast called. Querying catalog...")
    result = await db.execute(select(Product))
    products = result.scalars().all()
    return products


@app.get("/products/slow")
async def get_products_slow(db: AsyncSession = Depends(get_restricted_db)):  # noqa: B008
    """
    Slow endpoint: holds the database connection open for 1.0 second
    representing a slow query, large data fetch, or downstream API wait inside a transaction.
    """
    logger.warning("[FastAPI Request] /products/slow called. Querying and holding connection...")

    # We execute inside a transaction block to pin the connection to the session during the sleep
    async with db.begin():
        result = await db.execute(select(Product))
        products = result.scalars().all()

        # Simulate processing / slow query delay while holding the connection checked out!
        await asyncio.sleep(1.0)

    logger.success("[FastAPI Request] /products/slow completed. Releasing connection.")
    return products
