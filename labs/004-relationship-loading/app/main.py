from fastapi import Depends, FastAPI, status
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy.exc import MissingGreenlet
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload, selectinload

from app.dependencies import get_async_session, query_counter
from app.models import Comment, Post, User
from app.schemas import PostSchema


app = FastAPI(
    title="SQLAlchemy Relationship Loading strategies Lab API",
    description="Exposes endpoints demonstrating lazy loading failures (MissingGreenlet) and eager loading success.",
)


@app.exception_handler(MissingGreenlet)
async def missing_greenlet_exception_handler(request, exc: MissingGreenlet):
    """
    Catch standard MissingGreenlet exception and return a highly detailed 500 error,
    explaining why this failure happens in FastAPI async session serialization.
    """
    error_detail = (
        "SQLAlchemy MissingGreenlet Error! You attempted to access an unloaded "
        "lazy-loaded relationship during Pydantic serialization outside of an active database context. "
        "Under an async session, relationship lazy-loading is physically impossible because "
        "the serialization process runs synchronously and cannot await database requests. "
        "Fix this by using eager loading: joinedload() or selectinload()."
    )
    logger.error(f"[FastAPI Failure] MissingGreenlet raised: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error_type": "MissingGreenlet", "message": error_detail, "original_exception": str(exc)},
    )


@app.get("/posts/lazy", response_model=list[PostSchema])
async def get_posts_lazy(db: AsyncSession = Depends(get_async_session)):  # noqa: B008
    """
    Intentionally bad endpoint: fetches posts without any eager loading.
    Accessing nested properties in Pydantic serialization will trigger a MissingGreenlet exception.
    """
    query_counter.reset()
    query_counter.enable_logging(True)
    logger.info("[FastAPI Request] /posts/lazy called. Querying posts without eager loading...")

    # Fetch posts without relationship strategy (default is lazy loading)
    result = await db.execute(select(Post).limit(5))
    posts = result.scalars().all()

    logger.info(f"[FastAPI] Fetched {len(posts)} posts. Attempting to return via Pydantic schema...")
    # Returning this list directly will trigger serialization and raise MissingGreenlet
    return posts


@app.get("/posts/eager", response_model=list[PostSchema])
async def get_posts_eager(db: AsyncSession = Depends(get_async_session)):  # noqa: B008
    """
    Correct endpoint: eagerly loads all required relationships using optimal strategies:
    - joinedload() for One-to-One and Many-to-One relationships.
    - selectinload() for One-to-Many and Many-to-Many collections.
    """
    query_counter.reset()
    query_counter.enable_logging(True)
    logger.info("[FastAPI Request] /posts/eager called. Querying posts with eager loading...")

    # Build query with optimized loading strategies:
    # 1. joinedload for Post.author (Many-to-1) and Author's profile (1-to-1)
    # 2. selectinload for Post.comments (1-to-Many) and joinedload for Comment's author (Many-to-1)
    # 3. selectinload for Post.tags (Many-to-Many)
    stmt = (
        select(Post)
        .options(
            joinedload(Post.author).joinedload(User.profile),
            selectinload(Post.comments).joinedload(Comment.author),
            selectinload(Post.tags),
        )
        .limit(5)
    )

    result = await db.execute(stmt)
    posts = result.scalars().all()

    logger.info(f"[FastAPI] Fetched {len(posts)} posts. Total queries: {query_counter.count}")
    query_counter.enable_logging(False)
    return posts
