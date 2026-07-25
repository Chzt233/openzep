import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from deps import verify_api_key
from models.batch import (
    BatchAddItem,
    BatchCreateRequest,
    BatchItemDetail,
    BatchItemListResponse,
    BatchListResponse,
    BatchSummary,
)

router = APIRouter(prefix="/api/v2", tags=["batch"], dependencies=[Depends(verify_api_key)])

# 内存中的 Batch 存储
_batches: dict[str, BatchSummary] = {}
_batch_items: dict[str, list[BatchItemDetail]] = {}


def _now() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


@router.post("/batches", response_model=BatchSummary, status_code=status.HTTP_200_OK)
async def create_batch(body: BatchCreateRequest):
    """创建 Batch。"""
    batch_id = body.batch_id or str(uuid.uuid4())
    now = _now()
    batch = BatchSummary(
        batch_id=batch_id,
        description=body.description,
        status="pending",
        created_at=now,
        item_count=0,
    )
    _batches[batch_id] = batch
    _batch_items[batch_id] = []
    return batch


@router.get("/batches", response_model=BatchListResponse)
async def list_batches():
    """列出所有 Batch。"""
    items = list(_batches.values())
    return BatchListResponse(
        batches=items,
        total_count=len(items),
        row_count=len(items),
    )


@router.get("/batches/{batch_id}", response_model=BatchSummary)
async def get_batch(batch_id: str):
    """获取单个 Batch。"""
    batch = _batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch


@router.delete("/batches/{batch_id}", status_code=status.HTTP_200_OK)
async def delete_batch(batch_id: str):
    """删除 Batch 及其项目。"""
    if batch_id not in _batches:
        raise HTTPException(status_code=404, detail="Batch not found")
    del _batches[batch_id]
    _batch_items.pop(batch_id, None)
    return {"message": "Batch deleted", "batch_id": batch_id}


@router.post("/batches/{batch_id}/items", response_model=BatchItemListResponse, status_code=status.HTTP_200_OK)
async def add_batch_items(batch_id: str, body: list[BatchAddItem]):
    """向 Batch 添加项目。"""
    if batch_id not in _batches:
        raise HTTPException(status_code=404, detail="Batch not found")

    new_items = [
        BatchItemDetail(
            item_id=str(uuid.uuid4()),
            status="pending",
            payload=item.payload,
        )
        for item in body
    ]
    _batch_items.setdefault(batch_id, []).extend(new_items)
    _batches[batch_id].item_count = len(_batch_items[batch_id])

    return BatchItemListResponse(
        items=new_items,
        total_count=len(new_items),
        row_count=len(new_items),
    )


@router.get("/batches/{batch_id}/items", response_model=BatchItemListResponse)
async def list_batch_items(
    batch_id: str,
    limit: int = 100,
    cursor: int | None = None,
    status_filter: str | None = None,
):
    """列出 Batch 中的项目。"""
    if batch_id not in _batches:
        raise HTTPException(status_code=404, detail="Batch not found")

    items = _batch_items.get(batch_id, [])
    if status_filter:
        items = [item for item in items if item.status == status_filter]

    offset = cursor if cursor is not None else 0
    page = items[offset : offset + limit]
    return BatchItemListResponse(
        items=page,
        total_count=len(items),
        row_count=len(page),
    )


@router.post("/batches/{batch_id}/process", response_model=BatchSummary)
async def process_batch(batch_id: str):
    """处理 Batch，当前为占位实现。"""
    batch = _batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    for item in _batch_items.get(batch_id, []):
        item.status = "completed"
    batch.status = "processed"
    return batch
