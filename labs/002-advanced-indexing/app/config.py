import os

from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()


def get_db_uri() -> str:
    """
    Constructs and returns the database URI from environment variables.
    """
    db_host = os.getenv("POSTGRES_HOST", "localhost")
    db_port = os.getenv("POSTGRES_PORT", "5433")
    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_pass = os.getenv("POSTGRES_PASSWORD", "postgres")
    db_name = os.getenv("POSTGRES_DB", "advanced_indexing")

    return f"postgresql+psycopg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
