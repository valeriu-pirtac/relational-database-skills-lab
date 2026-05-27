"""
Lab Step 2: Collection Loading - subqueryload() vs. selectinload()

This script demonstrates:
1. Comparing subqueryload() and selectinload() for loading collections (One-to-Many / Many-to-Many).
2. The architectural differences in their SQL statements.
3. Why selectinload() is the modern default and generally preferred in SQLAlchemy 2.0,
   and how subqueryload() duplicates complex query blocks under pagination (LIMIT).
"""

from app.dependencies import SessionLocal, query_counter
from app.models import Post
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import selectinload, subqueryload


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def run_subqueryload_demo() -> None:
    """Demonstrate how subqueryload constructs its collection query."""
    print_separator("STRATEGY A: SUBQUERY LOADING (subqueryload)")
    session = SessionLocal()

    query_counter.reset()
    query_counter.enable_logging(True)

    logger.info("[Action] Fetching paginated posts (LIMIT 5) with subqueryload...")
    # Fetch only 5 posts eagerly loading their comments via subqueryload
    stmt = select(Post).limit(5).options(subqueryload(Post.comments))
    result = session.execute(stmt)
    posts = result.scalars().all()

    # Access comments to ensure they are loaded
    for post in posts:
        _ = [c.content for c in post.comments]

    query_counter.enable_logging(False)
    logger.info(f"[Complete] Fetched {len(posts)} posts using {query_counter.count} queries.")
    logger.warning(
        "[Architecture Observation] Notice how subqueryload executes a second query "
        "that fully DUPLICATES the original query as a subquery: "
        "'SELECT ... WHERE comments.post_id IN (SELECT id FROM posts LIMIT 5)'."
        "If the original query has complex JOINs, WHERE filters, or custom sort orderings, "
        "PostgreSQL is forced to plan and execute that expensive query block a second time!"
    )

    session.close()


def run_selectinload_demo() -> None:
    """Demonstrate how selectinload constructs its collection query."""
    print_separator("STRATEGY B: SELECTIN LOADING (selectinload)")
    session = SessionLocal()

    query_counter.reset()
    query_counter.enable_logging(True)

    logger.info("[Action] Fetching paginated posts (LIMIT 5) with selectinload...")
    # Fetch only 5 posts eagerly loading their comments via selectinload
    stmt = select(Post).limit(5).options(selectinload(Post.comments))
    result = session.execute(stmt)
    posts = result.scalars().all()

    # Access comments
    for post in posts:
        _ = [c.content for c in post.comments]

    query_counter.enable_logging(False)
    logger.info(f"[Complete] Fetched {len(posts)} posts using {query_counter.count} queries.")
    logger.success(
        "[Architecture Observation] Notice how selectinload executes a second query "
        "using a clean, direct IN clause: 'SELECT ... WHERE comments.post_id IN (1, 2, 3, 4, 5)'."
        "This query is extremely lightweight, uses the foreign key index, and avoids duplicating "
        "the main query, which is a major win for database performance and cache efficiency!"
    )

    session.close()


def main() -> None:
    logger.info("=============================================================")
    logger.info("LAB STEP 2: Collection Loading - subqueryload() vs. selectinload()")
    logger.info("=============================================================")

    # Run demonstrations
    run_subqueryload_demo()
    run_selectinload_demo()

    print_separator("SUMMARY OF RECOMMENDATIONS")
    logger.info(
        "1. Prefer selectinload() over subqueryload() for almost all collections in SQLAlchemy 2.0.\n"
        "2. selectinload() is simpler, doesn't duplicate original query structures, and performs better under pagination.\n"
        "3. Only use subqueryload() in very rare legacy environments or on databases that do not support composite IN-clause limits."
    )


if __name__ == "__main__":
    main()
