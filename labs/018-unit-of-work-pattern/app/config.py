import os

from dotenv import load_dotenv


load_dotenv()


def get_db_uri() -> str:
    db_host = os.getenv("POSTGRES_HOST", "localhost")
    db_port = os.getenv("POSTGRES_PORT", "5432")
    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_pass = os.getenv("POSTGRES_PASSWORD", "postgres")
    db_name = os.getenv("POSTGRES_DB", "unit_of_work")

    return f"postgresql+psycopg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
