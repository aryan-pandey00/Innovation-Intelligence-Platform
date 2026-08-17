from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import UserRole


class NotificationResponse(BaseModel):
    id: int
    kind: str
    priority: str
    title: str
    body: str
    link: str | None
    created_at: datetime
    occurred_at: datetime | None
    read_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class NotificationFeed(BaseModel):
    """The list and its unread count together."""
    unread: int
    generated: int
    items: list[NotificationResponse]


class BroadcastCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    body: str = Field(min_length=3, max_length=2000)
    roles: list[UserRole] = []
    link: str | None = Field(default=None, max_length=300)

    @field_validator("title", "body")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        cleaned = " ".join(v.split())
        if len(cleaned) < 3:
            raise ValueError("must not be blank")
        return cleaned
