from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all Declarative SQLAlchemy models."""

    pass


class User(Base):
    """ORM representation of platform users."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)

    # 1-to-1 relationship with UserProfile
    profile: Mapped["UserProfile"] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"


class UserProfile(Base):
    """ORM representation of biographical profile metadata for a User."""

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    bio: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user: Mapped["User"] = relationship(back_populates="profile")

    def __repr__(self) -> str:
        return f"<UserProfile(id={self.id}, first_name='{self.first_name}', last_name='{self.last_name}')>"


class Product(Base):
    """ORM representation of catalog items containing a flexible specs JSONB document."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(nullable=False)

    # JSONB column storing semi-structured metadata
    specs: Mapped[dict] = mapped_column(JSONB, nullable=False)

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name='{self.name}', price={self.price})>"
