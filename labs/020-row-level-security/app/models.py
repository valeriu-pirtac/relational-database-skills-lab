from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, name='{self.name}')>"


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    content = Column(String, nullable=False)

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, tenant_id={self.tenant_id}, content='{self.content}')>"
