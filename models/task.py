from typing import Any

from pydantic import BaseModel, Field


class GetTaskResponse(BaseModel):
    """任务状态响应。"""

    task_id: str
    status: str = "completed"
    result: dict[str, Any] = Field(default_factory=dict)
