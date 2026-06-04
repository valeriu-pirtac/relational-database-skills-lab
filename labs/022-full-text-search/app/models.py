from sqlalchemy import Column, Computed, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)

    # In PostgreSQL 12+, we can use GENERATED ALWAYS AS (...) STORED
    # This automatically computes the tsvector on INSERT/UPDATE without needing triggers.
    search_vector = Column(
        TSVECTOR, Computed("to_tsvector('english', coalesce(title, '') || ' ' || coalesce(body, ''))", persisted=True)
    )

    def __repr__(self) -> str:
        return f"<Article(id={self.id}, title='{self.title}')>"


# Create a Generalized Inverted Index (GIN) on the computed tsvector column
Index("ix_articles_search_vector", Article.search_vector, postgresql_using="gin")
