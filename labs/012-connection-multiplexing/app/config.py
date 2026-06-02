import os

from dotenv import load_dotenv


# Load environment variables
load_dotenv()


def get_db_user() -> str:
    return os.getenv("POSTGRES_USER", "postgres")


def get_db_pass() -> str:
    return os.getenv("POSTGRES_PASSWORD", "postgres")


def get_db_name() -> str:
    return os.getenv("POSTGRES_DB", "multiplexing_db")


def get_db_host() -> str:
    return os.getenv("POSTGRES_HOST", "localhost")


def get_direct_db_uri() -> str:
    """Returns database URI directly to PostgreSQL (bypassing PgBouncer)."""
    user = get_db_user()
    pw = get_db_pass()
    host = get_db_host()
    port = os.getenv("POSTGRES_PORT", "5432")
    db = get_db_name()
    return f"postgresql+psycopg://{user}:{pw}@{host}:{port}/{db}"


def get_session_bouncer_uri() -> str:
    """Returns database URI via PgBouncer in Session mode."""
    user = get_db_user()
    pw = get_db_pass()
    host = get_db_host()
    port = os.getenv("BOUNCER_SESSION_PORT", "6430")
    db = get_db_name()
    return f"postgresql+psycopg://{user}:{pw}@{host}:{port}/{db}"


def get_transaction_bouncer_uri() -> str:
    """Returns database URI via PgBouncer in Transaction mode."""
    user = get_db_user()
    pw = get_db_pass()
    host = get_db_host()
    port = os.getenv("BOUNCER_TRANSACTION_PORT", "6431")
    db = get_db_name()
    return f"postgresql+psycopg://{user}:{pw}@{host}:{port}/{db}"


def get_bouncer_admin_uri(port_env_name: str) -> str:
    """
    Returns the URI to connect to PgBouncer's administrative 'pgbouncer' virtual DB.
    """
    user = get_db_user()
    pw = get_db_pass()
    host = get_db_host()
    port = os.getenv(port_env_name, "6431")
    # Administrative virtual DB is always 'pgbouncer'
    return f"postgresql+psycopg://{user}:{pw}@{host}:{port}/pgbouncer"
