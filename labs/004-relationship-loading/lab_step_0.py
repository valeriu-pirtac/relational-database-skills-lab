"""
Lab Step 0: The N+1 Query Problem & Default Lazy Loading

This script demonstrates:
1. Populating a mock e-commerce/blogging database with relational schema.
2. The core mechanism of the N+1 Query Problem using default SQLAlchemy lazy loading.
3. Quantifying exact database queries and latencies under lazy-loading.
"""

from app.dependencies import get_session_factory, init_db, query_counter
from app.models import Comment, Post, Tag, User, UserProfile
from faker import Faker
from loguru import logger
from sqlalchemy import select


def seed_database(session) -> None:
    """Populates the database with structured mock data using Faker."""
    logger.info("[Seed] Seeding database with realistic mock data...")
    fake = Faker()

    # 1. Create Tags
    tags = [Tag(name=name) for name in ["Tech", "Databases", "Python", "Web", "SystemDesign"]]
    session.add_all(tags)
    session.flush()

    # 2. Create Users, UserProfiles, Posts, and Comments
    for i in range(10):
        # Create User
        username = f"user_{i}_{fake.unique.user_name()}"
        user = User(username=username, email=fake.unique.email())
        session.add(user)
        session.flush()

        # Create Profile (1-to-1)
        profile = UserProfile(user_id=user.id, bio=fake.sentence(nb_words=10), avatar_url=fake.image_url())
        session.add(profile)

        # Create Posts (1-to-Many) for each user
        for _ in range(5):
            post = Post(author_id=user.id, title=fake.sentence(nb_words=6), content=fake.paragraph(nb_sentences=4))
            # Link Many-to-Many tags (2 tags per post)
            post.tags.extend([tags[i % 5], tags[(i + 1) % 5]])
            session.add(post)
            session.flush()

            # Create Comments (1-to-Many) for each post
            for _ in range(2):
                comment = Comment(
                    post_id=post.id,
                    author_id=user.id,  # Author commenting on their own/other posts
                    content=fake.sentence(nb_words=8),
                )
                session.add(comment)

    session.commit()
    logger.info("[Seed] Successfully seeded 10 Users, 10 Profiles, 50 Posts, 100 Comments, and 5 Tags.")


def simulate_n_plus_one_problem() -> None:
    """Simulate lazy-loading posts and accessing relationships, demonstrating the N+1 issue."""
    session_factory = get_session_factory()

    with session_factory() as session:
        # Reset and enable query logger
        query_counter.reset()
        query_counter.enable_logging(True)

        logger.info("\n=== [SIMULATION] Fetching 50 Posts (Standard select(Post)) ===")
        # 1. Query for posts (This is the "1" query in N+1)
        result = session.execute(select(Post))
        posts = result.scalars().all()
        logger.info(
            f"Initial query complete. Loaded {len(posts)} posts. Queries executed so far: {query_counter.count}"
        )

        logger.info("\n=== [SIMULATION] Accessing author for each post (Lazy Loading) ===")
        # 2. Iterate through posts and access the lazy-loaded relationship 'author'
        # This will trigger an individual SELECT query for EACH post (The "N" queries)
        authors = []
        for post in posts:
            authors.append(post.author.username)

        logger.info(f"Loaded authors for all posts. Queries executed so far: {query_counter.count}")

        logger.info("\n=== [SIMULATION] Accessing bio inside user profile (1-to-1 Lazy Loading) ===")
        # 3. Iterate through authors and access their 1-to-1 'profile' relationship
        # This triggers another N queries!
        bios = []
        for post in posts:
            bios.append(post.author.profile.bio)

        logger.info(f"Loaded profiles for all authors. Queries executed so far: {query_counter.count}")

        # Disable logging and print results
        query_counter.enable_logging(False)

        total_queries = query_counter.count
        logger.warning(
            f"\n"
            f"--------------------------------------------------\n"
            f"   N+1 Query Simulation Results:\n"
            f"   Posts Loaded (N):       {len(posts)}\n"
            f"   Initial Query (1):      1\n"
            f"   Author Lookups (N):     {len(posts)}\n"
            f"   Profile Lookups (N):    {len(posts)}\n"
            f"   ----------------------------------\n"
            f"   Total SQL Queries Run:  {total_queries} queries!\n"
            f"--------------------------------------------------"
        )
        logger.info(
            "[Key Insight] Default lazy loading causes a massive database query explosion. "
            "Under traffic spikes, this results in high latencies, thread starvation, and connection pool exhaustion!"
        )


def main() -> None:
    logger.info("=============================================================")
    logger.info("LAB STEP 0: The N+1 Query Problem & Default Lazy Loading")
    logger.info("=============================================================")

    # Initialize schema and seed data
    init_db()
    session_factory = get_session_factory()
    with session_factory() as session:
        seed_database(session)

    # Run the N+1 simulation
    simulate_n_plus_one_problem()

    logger.info("=============================================================")
    logger.info("Lab Step 0 Complete!")
    logger.info("=============================================================")


if __name__ == "__main__":
    # Custom get_session_factory mapping to match standard SessionLocal
    def get_session_factory():
        from app.dependencies import SessionLocal

        return SessionLocal

    main()
