from app.config import get_db_uri
from sqlalchemy import create_engine, text


engine = create_engine(get_db_uri())
with engine.begin() as conn:
    conn.execute(text("ALTER ROLE postgres NOBYPASSRLS;"))
    print("Without tenant:", conn.execute(text("SELECT * FROM documents")).fetchall())
