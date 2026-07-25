from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from deps import verify_api_key
from models.project import (
    ObservationSteeringConfig,
    ObservationSteeringUpdateRequest,
    ProjectInfoResponse,
    ProjectInfoUpdateRequest,
)

router = APIRouter(prefix="/api/v2", tags=["project"], dependencies=[Depends(verify_api_key)])

# 项目信息存储在内存中，进程重启后恢复默认值
_project_info: dict = {
    "uuid": "default",
    "name": "OpenZep",
    "description": "Self-hosted Zep API-compatible memory service",
    "default_time_zone": "UTC",
}

_observation_steering: dict = ObservationSteeringConfig().model_dump()


def _now() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


@router.get("/projects/info", response_model=ProjectInfoResponse)
async def get_project_info():
    """获取项目信息。"""
    data = dict(_project_info)
    data.setdefault("created_at", _now())
    data.setdefault("updated_at", _now())
    return ProjectInfoResponse(**data)


@router.patch("/projects/info", response_model=ProjectInfoResponse)
async def update_project_info(body: ProjectInfoUpdateRequest):
    """更新项目信息，目前主要支持 default_time_zone。"""
    if body.name is not None:
        _project_info["name"] = body.name
    if body.description is not None:
        _project_info["description"] = body.description
    if body.default_time_zone is not None:
        _project_info["default_time_zone"] = body.default_time_zone
    _project_info["updated_at"] = _now()
    return ProjectInfoResponse(**_project_info)


@router.get("/projects/observation-steering", response_model=ObservationSteeringConfig)
async def get_observation_steering():
    """获取观察转向配置占位。"""
    return ObservationSteeringConfig(**_observation_steering)


@router.put("/projects/observation-steering", response_model=ObservationSteeringConfig)
async def update_observation_steering(body: ObservationSteeringUpdateRequest):
    """更新观察转向配置占位。"""
    if body.enabled is not None:
        _observation_steering["enabled"] = body.enabled
    if body.instructions is not None:
        _observation_steering["instructions"] = body.instructions
    return ObservationSteeringConfig(**_observation_steering)
