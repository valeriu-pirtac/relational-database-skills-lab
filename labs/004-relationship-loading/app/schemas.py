from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserProfileSchema(BaseModel):
    """Pydantic model for UserProfile details."""

    model_config = ConfigDict(from_attributes=True)

    bio: str | None = None
    avatar_url: str | None = None


class UserSchema(BaseModel):
    """Pydantic model for User details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    profile: UserProfileSchema | None = None


class TagSchema(BaseModel):
    """Pydantic model for Tag details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CommentSchema(BaseModel):
    """Pydantic model for Comment details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    author: UserSchema
    created_at: datetime


class PostSchema(BaseModel):
    """Pydantic model for Post details including loaded relationships."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    created_at: datetime
    author: UserSchema
    comments: list[CommentSchema] = []
    tags: list[TagSchema] = []
