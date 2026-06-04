from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    salary = Column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<Employee(id={self.id}, name='{self.name}')>"
