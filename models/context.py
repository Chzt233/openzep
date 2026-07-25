from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ContextTemplate(BaseModel):
    """上下文模板模型。"""

    template_id: str
    name: str
    template: str
    description: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ContextTemplateCreateRequest(BaseModel):
    """创建上下文模板的请求体。"""

    name: str
    template: str
    description: str = ""


class ContextTemplateUpdateRequest(BaseModel):
    """更新上下文模板的请求体。"""

    name: str | None = None
    template: str | None = None
    description: str | None = None


class ContextTemplateResponse(ContextTemplate):
    """上下文模板响应。"""

    pass


class ListContextTemplatesResponse(BaseModel):
    """上下文模板列表响应。"""

    templates: list[ContextTemplateResponse] = Field(default_factory=list)
    total_count: int = 0
    row_count: int = 0
