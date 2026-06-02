import os

from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()


def get_primary_db_uri() -> str:
    """Construct and return the primary database URI from environment variables."""
    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_pass = os.getenv("POSTGRES_PASSWORD", "postgres")
    db_name = os.getenv("POSTGRES_DB", "scaling_topology")
    db_host = os.getenv("PRIMARY_HOST", "localhost")
    db_port = os.getenv("PRIMARY_PORT", "5432")

    return f"postgresql+psycopg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"


def get_replica_db_uri() -> str:
    """Construct and return the replica database URI from environment variables."""
    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_pass = os.getenv("POSTGRES_PASSWORD", "postgres")
    db_name = os.getenv("POSTGRES_DB", "scaling_topology")
    db_host = os.getenv("REPLICA_HOST", "localhost")
    db_port = os.getenv("REPLICA_PORT", "5433")

    return f"postgresql+psycopg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
