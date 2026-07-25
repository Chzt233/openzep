from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ThreadCreateRequest(BaseModel):
    """创建 Thread 的请求体，thread_id 可选，未提供时由服务端生成。"""

    thread_id: str | None = None
    user_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Thread(BaseModel):
    """Thread 响应模型；在 OpenZep 内部复用 sessions 表存储。"""

    uuid: str
    thread_id: str
    user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ThreadListResponse(BaseModel):
    """Thread 列表响应。"""

    threads: list[Thread] = Field(default_factory=list)
    total_count: int = 0
    row_count: int = 0


class Message(BaseModel):
    """Thread 中的单条消息模型。"""

    uuid: str | None = None
    role: str
    content: str
    role_type: str | None = None
    created_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MessageListResponse(BaseModel):
    """Thread 消息列表响应。"""

    messages: list[Message] = Field(default_factory=list)
    total_count: int = 0
    row_count: int = 0


class AddThreadMessagesRequest(BaseModel):
    """向 Thread 追加消息的请求体。"""

    messages: list[Message]
    ignore_roles: list[str] | None = Field(default=None)
    return_context: bool = False
    strict_ontology: bool = False


class AddThreadMessagesResponse(BaseModel):
    """向 Thread 追加消息的响应。"""

    ok: bool = True


class ThreadSummary(BaseModel):
    """Thread 摘要占位模型。"""

    uuid: str
    created_at: datetime | None = None
    content: str = ""


class ThreadContextResponse(BaseModel):
    """Thread 上下文响应。"""

    context: str = ""
    messages: list[Message] = Field(default_factory=list)
