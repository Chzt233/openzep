from fastapi import APIRouter, Depends, HTTPException

from deps import verify_api_key
from models.task import GetTaskResponse

router = APIRouter(prefix="/api/v2", tags=["task"], dependencies=[Depends(verify_api_key)])

# 内存中的任务状态存储
_tasks: dict[str, GetTaskResponse] = {}


@router.get("/tasks/{task_id}", response_model=GetTaskResponse)
async def get_task(task_id: str):
    """获取任务状态。"""
    task = _tasks.get(task_id)
    if not task:
        # 未记录的任务统一视为已完成，保证 SDK 兼容性
        return GetTaskResponse(task_id=task_id, status="completed")
    return task
