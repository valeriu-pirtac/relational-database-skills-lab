"""
Lab Step 1: Eager Loading with joinedload() vs. selectinload()

This script demonstrates:
1. Eliminating the N+1 problem using SQLAlchemy's joinedload() and selectinload() strategies.
2. The difference in execution plans, query counts, and latencies.
3. Why joinedload is ideal for 1-to-1 / Many-to-1, and selectinload is optimal for collections (1-to-Many, Many-to-Many).
"""

import time

from app.dependencies import SessionLocal, query_counter
from app.models import Comment, Post, User
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def run_lazy_loading_benchmark() -> float:
    """Measure performance and query count of lazy-loading relationships."""
    print_separator("STRATEGY 1: LAZY LOADING (N+1)")
    session = SessionLocal()

    query_counter.reset()
    query_counter.enable_logging(False)  # Keep logging off during benchmark for speed

    start_time = time.time()
    # 1. Fetch posts
    result = session.execute(select(Post))
    posts = result.scalars().all()

    # 2. Lazy load authors, profiles, and tags sequentially
    for post in posts:
        _ = post.author.username
        _ = post.author.profile.bio
        _ = [t.name for t in post.tags]
        _ = [c.content for c in post.comments]

    elapsed = time.time() - start_time
    logger.info(f"[Lazy Loading] Fetched {len(posts)} posts and resolved relationships.")
    logger.info(f"[Lazy Loading] Execution Time: {elapsed * 1000:.2f} ms")
    logger.warning(f"[Lazy Loading] Total Database Queries: {query_counter.count}")

    session.close()
    return elapsed


def run_joined_loading_benchmark() -> float:
    """Measure performance and query count of joinedload (eager join loading)."""
    print_separator("STRATEGY 2: EAGER JOINED LOADING (joinedload)")
    session = SessionLocal()

    query_counter.reset()
    query_counter.enable_logging(True)  # Turn logging on to see the massive single join query

    start_time = time.time()
    # Query posts, eagerly outer joining author, profile, tags, and comments
    stmt = select(Post).options(
        joinedload(Post.author).joinedload(User.profile), joinedload(Post.comments), joinedload(Post.tags)
    )

    result = session.execute(stmt)
    posts = result.scalars().unique().all()  # unique() is required when joining collections to prevent duplicates

    # Access fields - no extra database queries will be triggered
    for post in posts:
        _ = post.author.username
        _ = post.author.profile.bio
        _ = [t.name for t in post.tags]
        _ = [c.content for c in post.comments]

    elapsed = time.time() - start_time
    query_counter.enable_logging(False)

    logger.info(f"[Joinedload] Fetched {len(posts)} posts and resolved relationships.")
    logger.info(f"[Joinedload] Execution Time: {elapsed * 1000:.2f} ms")
    logger.success(f"[Joinedload] Total Database Queries: {query_counter.count} (Perfect 1 query!)")

    session.close()
    return elapsed


def run_selectin_loading_benchmark() -> float:
    """Measure performance and query count of selectinload (eager select-in loading)."""
    print_separator("STRATEGY 3: EAGER SELECTIN LOADING (selectinload)")
    session = SessionLocal()

    query_counter.reset()
    query_counter.enable_logging(True)  # Turn logging on to inspect separate queries

    start_time = time.time()
    # Query posts, joined-loading 1-to-1 relationships and selectin-loading collections
    stmt = select(Post).options(
        joinedload(Post.author).joinedload(User.profile),  # 1-to-1 / Many-to-1 uses joinedload
        selectinload(Post.comments).joinedload(Comment.author),  # Collections use selectinload
        selectinload(Post.tags),  # Collections use selectinload
    )

    result = session.execute(stmt)
    posts = result.scalars().all()  # No unique() required with selectinload

    # Access fields - no extra queries triggered
    for post in posts:
        _ = post.author.username
        _ = post.author.profile.bio
        _ = [t.name for t in post.tags]
        _ = [c.content for c in post.comments]

    elapsed = time.time() - start_time
    query_counter.enable_logging(False)

    logger.info(f"[Selectinload] Fetched {len(posts)} posts and resolved relationships.")
    logger.info(f"[Selectinload] Execution Time: {elapsed * 1000:.2f} ms")
    logger.success(f"[Selectinload] Total Database Queries: {query_counter.count} (Only 3 clean queries!)")

    session.close()
    return elapsed


def main() -> None:
    logger.info("=============================================================")
    logger.info("LAB STEP 1: Eager Loading - joinedload() vs. selectinload()")
    logger.info("=============================================================")

    # Run the benchmarks
    lazy_time = run_lazy_loading_benchmark()
    joined_time = run_joined_loading_benchmark()
    selectin_time = run_selectin_loading_benchmark()

    print_separator("BENCHMARK COMPARISON SUMMARY")
    logger.info(f"Lazy Loading (N+1):       {lazy_time * 1000:.2f} ms")
    logger.info(f"Joined Eager Loading:     {joined_time * 1000:.2f} ms")
    logger.info(f"Selectin Eager Loading:   {selectin_time * 1000:.2f} ms")

    logger.info("\n=== [Production Gotcha: The Cartesian Product Nightmare] ===")
    logger.warning(
        "While joinedload() achieves exactly 1 query, applying it to multiple collections "
        "(like both comments AND tags) causes PostgreSQL to generate a massive Cartesian Product. "
        "Every row in comments is multiplied by every row in tags, inflating the volume of data "
        "sent across the network. For collections, selectinload() is far more performant because "
        "it fetches related tables in clean, separate, non-mutliplying queries using WHERE IN."
    )


if __name__ == "__main__":
    main()
