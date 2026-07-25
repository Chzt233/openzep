from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BatchAddItem(BaseModel):
    """批量任务中的单个操作项。"""

    operation: str = "add_message"
    payload: dict[str, Any] = Field(default_factory=dict)


class BatchItemDetail(BaseModel):
    """批量任务项详情。"""

    item_id: str
    status: str = "pending"
    payload: dict[str, Any] = Field(default_factory=dict)


class BatchCreateRequest(BaseModel):
    """创建 Batch 的请求体。"""

    batch_id: str | None = None
    description: str = ""


class Batch(BaseModel):
    """Batch 基础模型。"""

    batch_id: str
    description: str = ""
    status: str = "pending"
    created_at: datetime | None = None


class BatchSummary(Batch):
    """Batch 摘要，包含项目数量。"""

    item_count: int = 0


class BatchItemListResponse(BaseModel):
    """Batch 项目列表响应。"""

    items: list[BatchItemDetail] = Field(default_factory=list)
    total_count: int = 0
    row_count: int = 0


class BatchListResponse(BaseModel):
    """Batch 列表响应。"""

    batches: list[BatchSummary] = Field(default_factory=list)
    total_count: int = 0
    row_count: int = 0
