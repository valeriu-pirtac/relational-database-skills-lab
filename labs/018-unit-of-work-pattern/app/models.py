from sqlalchemy import CheckConstraint, Column, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    owner_name = Column(String(100), nullable=False, unique=True)
    balance = Column(Numeric(10, 2), nullable=False)

    __table_args__ = (CheckConstraint("balance >= 0", name="check_positive_balance"),)

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, owner_name='{self.owner_name}', balance={self.balance})>"
