import os


def get_db_uri() -> str:
    """
    Constructs and returns the database URI from the environment variables.
    """
    db_host = os.getenv("POSTGRES_HOST")
    db_port = os.getenv("POSTGRES_PORT")
    db_user = os.getenv("POSTGRES_USER")
    db_pass = os.getenv("POSTGRES_PASSWORD")
    db_name = os.getenv("POSTGRES_DB")

    return f"postgresql+psycopg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
