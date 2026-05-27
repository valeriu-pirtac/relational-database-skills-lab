from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for Declarative SQLAlchemy models."""

    pass


# Association table for Many-to-Many relationship between Post and Tag
post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    """Represents a platform user / author."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 1-to-1 relationship with UserProfile
    # uselist=False makes it a 1-to-1 relationship instead of 1-to-Many
    profile = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # 1-to-Many relationship with Post
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")

    # 1-to-Many relationship with Comment
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")


class UserProfile(Base):
    """1-to-1 profile extension for User."""

    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    bio = Column(String(255))
    avatar_url = Column(String(255))

    # Back reference to User
    user = relationship("User", back_populates="profile")


class Post(Base):
    """Represents a blog post."""

    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Many-to-1 relationship back to User
    author = relationship("User", back_populates="posts")

    # 1-to-Many relationship with Comment
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")

    # Many-to-Many relationship with Tag
    tags = relationship("Tag", secondary=post_tags, back_populates="posts")


class Comment(Base):
    """Represents a comment on a blog post."""

    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Many-to-1 relationship with Post
    post = relationship("Post", back_populates="comments")

    # Many-to-1 relationship with User
    author = relationship("User", back_populates="comments")


class Tag(Base):
    """Represents a post tag for categorization."""

    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(30), unique=True, nullable=False, index=True)

    # Many-to-Many back reference to Post
    posts = relationship("Post", secondary=post_tags, back_populates="tags")
