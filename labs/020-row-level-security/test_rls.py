from app.config import get_db_uri
from sqlalchemy import create_engine, text


engine = create_engine(get_db_uri())
with engine.begin() as conn:
    conn.execute(text("DROP ROLE IF EXISTS rls_user;"))
    conn.execute(text("CREATE ROLE rls_user;"))
    conn.execute(text("GRANT ALL ON documents TO rls_user;"))
    conn.execute(text("GRANT ALL ON tenants TO rls_user;"))
    conn.execute(text("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO rls_user;"))

with engine.begin() as conn:
    conn.execute(text("SET ROLE rls_user;"))
    print("Without tenant:", conn.execute(text("SELECT * FROM documents")).fetchall())
    conn.execute(text("SET LOCAL app.current_tenant = '1';"))
    print("With tenant:", conn.execute(text("SELECT * FROM documents")).fetchall())
