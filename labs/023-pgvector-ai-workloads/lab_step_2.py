"""
Lab Step 2: Approximate Nearest Neighbor (ANN) Indexing (HNSW)
"""

from app.dependencies import SessionLocal, default_sync_engine
from loguru import logger
from sqlalchemy import text


def print_separator(title: str) -> None:
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def run_explain(session, search_embedding) -> str:
    # Convert python list to Postgres vector string format '[0.1, 0.2, 0.3]'
    vec_str = f"[{','.join(map(str, search_embedding))}]"

    explain_query = text(f"""
        EXPLAIN SELECT id
        FROM document_chunks
        ORDER BY embedding <=> '{vec_str}'
        LIMIT 2
    """)
    result = session.execute(explain_query)
    return "\n".join([row[0] for row in result])


def main():
    print_separator("ANALYZING THE EXACT KNN (SEQ SCAN) BOTTLENECK")
    with SessionLocal() as session:
        search_embedding = [0.05, 0.85, 0.35]

        logger.warning("Running EXPLAIN on the Cosine Distance sort...")
        plan = run_explain(session, search_embedding)
        logger.info(f"EXPLAIN Plan:\n{plan}")
        logger.error(
            "Observe the 'Seq Scan' and 'Sort'. To find the 2 closest vectors, PostgreSQL had to calculate the distance against EVERY single row in the table, and then sort them all. This is O(N) and fails at scale."
        )

    print_separator("BUILDING AN HNSW INDEX")
    with default_sync_engine.begin() as conn:
        logger.warning("Creating a Hierarchical Navigable Small World (HNSW) Index...")
        # We specify vector_cosine_ops because we sort using <=> (Cosine Distance)
        # m = max number of connections per layer, ef_construction = size of the dynamic candidate list
        conn.execute(
            text("""
            CREATE INDEX ix_docs_embedding_hnsw
            ON document_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
        """)
        )
        logger.success("HNSW Index built successfully!")

    print_separator("VERIFYING THE ANN INDEX SPEEDUP")
    with SessionLocal() as session:
        # In order for Postgres to use the HNSW index in EXPLAIN with only 5 rows,
        # we must disable sequential scans temporarily to force the query planner to show the Index path.
        session.execute(text("SET enable_seqscan = off;"))
        plan = run_explain(session, search_embedding)
        logger.info(f"EXPLAIN Plan (With HNSW):\n{plan}")
        logger.success(
            "Observe the 'Index Scan using ix_docs_embedding_hnsw'! PostgreSQL is now executing an Approximate Nearest Neighbor (ANN) search. It traverses a graph rather than scanning the whole table, resulting in sub-millisecond AI searches at massive scale."
        )


if __name__ == "__main__":
    # Note: Assumes lab_step_1 was run first to initialize the database schema and seed data
    main()
