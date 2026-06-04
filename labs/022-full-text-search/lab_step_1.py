"""
Lab Step 1: Text Search Primitives and GIN Indexing
"""

from app.dependencies import SessionLocal, init_db
from app.models import Article
from loguru import logger
from sqlalchemy import text


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def run_explain(session, query_str: str, params: dict) -> str:
    explain_query = text(f"EXPLAIN {query_str}")
    result = session.execute(explain_query, params)
    return "\n".join([row[0] for row in result])


def main():
    init_db()

    print_separator("SEEDING ARTICLE DATA")
    with SessionLocal() as session:
        articles = [
            Article(
                title="Introduction to PostgreSQL",
                body="PostgreSQL is an advanced, enterprise-class open-source relational database.",
            ),
            Article(
                title="FastAPI Web Framework",
                body="FastAPI is a modern, fast (high-performance), web framework for building APIs with Python.",
            ),
            Article(
                title="Advanced Search Techniques",
                body="To search effectively, one must understand how relational databases parse and index text.",
            ),
            Article(
                title="The Anatomy of a GIN Index",
                body="Generalized Inverted Indexes are extremely fast for array and full-text search operations in PostgreSQL.",
            ),
            Article(
                title="Python and Databases",
                body="Python pairs incredibly well with relational databases, especially using ORMs like SQLAlchemy.",
            ),
        ]
        session.add_all(articles)
        session.commit()
        logger.success("Seeded 5 articles into the database.")

    print_separator("TESTING GIN INDEX EFFICIENCY")
    with SessionLocal() as session:
        # 1. Standard LIKE query (Forces a Sequential Scan)
        logger.warning("[App] Running a standard ILIKE query for '%database%'...")
        like_query = "SELECT title FROM articles WHERE body ILIKE :term"
        like_plan = run_explain(session, like_query, {"term": "%database%"})
        logger.info(f"EXPLAIN Plan (ILIKE):\n{like_plan}")
        logger.error("Notice the 'Seq Scan' above. ILIKE cannot use standard B-Tree indexes for leading wildcards!")

        # 2. Native Full-Text Search using @@ (Leverages the GIN Index)
        logger.warning("[App] Running a Native Full-Text Search for 'database'...")
        # Because our table only has 5 rows, Postgres will normally use a Seq Scan because
        # reading 1 disk page is faster than traversing an index. We turn seqscan off to prove the index works.
        session.execute(text("SET enable_seqscan = off;"))
        fts_query = "SELECT title FROM articles WHERE search_vector @@ to_tsquery('english', :term)"
        fts_plan = run_explain(session, fts_query, {"term": "database"})
        logger.info(f"EXPLAIN Plan (FTS):\n{fts_plan}")
        logger.success(
            "Notice the 'Bitmap Index Scan' on 'ix_articles_search_vector'! The GIN index was successfully used."
        )
        session.execute(text("SET enable_seqscan = on;"))


if __name__ == "__main__":
    main()
