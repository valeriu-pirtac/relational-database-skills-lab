import os

from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()


def get_db_uri(is_async: bool = False) -> str:
    """
    Constructs and returns the database URI from environment variables,
    supporting both sync (psycopg) and async (asyncpg) dialects.
    """
    db_host = os.getenv("POSTGRES_HOST", "localhost")
    db_port = os.getenv("POSTGRES_PORT", "5434")
    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_pass = os.getenv("POSTGRES_PASSWORD", "postgres")
    db_name = os.getenv("POSTGRES_DB", "relationship_loading")

    dialect = "postgresql+asyncpg" if is_async else "postgresql+psycopg"
    return f"{dialect}://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"


DATABASE_URL = get_db_uri(is_async=False)
ASYNC_DATABASE_URL = get_db_uri(is_async=True)
