from pgvector.sqlalchemy import Vector  # type: ignore
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True)
    content = Column(String, nullable=False)

    # Using a 3-dimensional vector for easy visualization in the lab.
    # Production LLMs (like OpenAI text-embedding-3-small) output 1536 dimensions.
    embedding = Column(Vector(3))

    def __repr__(self) -> str:
        return f"<DocumentChunk(id={self.id}, content='{self.content}')>"
