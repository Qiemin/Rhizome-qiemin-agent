from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(default="新会话", min_length=1, max_length=200)
    workspace_id: str | None = Field(default=None, max_length=100)


class SessionRename(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=1, max_length=200)


class SessionResponse(BaseModel):
    session_id: str
    workspace_id: str | None = None
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class SessionList(BaseModel):
    items: list[SessionResponse]
    total: int
    limit: int
    offset: int


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    name: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class MessageList(BaseModel):
    session_id: str
    messages: list[MessageResponse]
