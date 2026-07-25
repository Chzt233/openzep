from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProjectInfoResponse(BaseModel):
    """项目信息响应。"""

    uuid: str = "default"
    name: str = "OpenZep"
    description: str = ""
    default_time_zone: str = "UTC"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectInfoUpdateRequest(BaseModel):
    """更新项目信息的请求体。"""

    name: str | None = None
    description: str | None = None
    default_time_zone: str | None = None


class ObservationSteeringConfig(BaseModel):
    """观察转向配置占位模型。"""

    enabled: bool = False
    instructions: list[str] = Field(default_factory=list)


class ObservationSteeringUpdateRequest(BaseModel):
    """更新观察转向配置的请求体。"""

    enabled: bool | None = None
    instructions: list[str] | None = None
