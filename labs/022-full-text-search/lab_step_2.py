"""
Lab Step 2: Advanced Search (Ranking, Highlighting, and Dictionaries)
"""

from app.dependencies import SessionLocal
from loguru import logger
from sqlalchemy import text


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def main():
    print_separator("QUERY PARSING & LEXEMES (Stemming)")
    with SessionLocal() as session:
        # Let's show how Postgres parses text into stems/lexemes
        raw_string = "The advanced databases are searching quickly!"
        parsed = session.execute(text("SELECT to_tsvector('english', :text)"), {"text": raw_string}).scalar()
        logger.info(f"Raw String: '{raw_string}'")
        logger.success(f"Parsed tsvector: {parsed}")
        logger.info(
            "Notice how 'databases' became 'databas', 'searching' became 'search', and stop words ('the', 'are') were completely removed!"
        )

    print_separator("RANKING RESULTS (ts_rank)")
    with SessionLocal() as session:
        # Using ts_rank to sort by relevance
        logger.warning("Searching for 'relational & database' and ordering by relevance rank...")
        query = """
            SELECT
                title,
                ts_rank(search_vector, to_tsquery('english', 'relational & database')) as rank
            FROM articles
            WHERE search_vector @@ to_tsquery('english', 'relational & database')
            ORDER BY rank DESC;
        """
        results = session.execute(text(query)).fetchall()
        for row in results:
            logger.success(f"Score: {row.rank:.4f} | Title: {row.title}")

    print_separator("HIGHLIGHTING SNIPPETS (ts_headline)")
    with SessionLocal() as session:
        # Using ts_headline to generate HTML bold tags around matches
        logger.warning("Generating search result snippets for the UI...")
        query = """
            SELECT
                title,
                ts_headline('english', body, to_tsquery('english', 'fast | database')) as snippet
            FROM articles
            WHERE search_vector @@ to_tsquery('english', 'fast | database');
        """
        results = session.execute(text(query)).fetchall()
        for row in results:
            logger.info(f"Title: {row.title}")
            logger.success(f"Snippet: {row.snippet}")


if __name__ == "__main__":
    # Note: Assumes lab_step_1.py was run first to initialize the database schema and seed data
    main()
