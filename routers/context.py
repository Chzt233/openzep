import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from deps import verify_api_key
from models.context import (
    ContextTemplate,
    ContextTemplateCreateRequest,
    ContextTemplateResponse,
    ContextTemplateUpdateRequest,
    ListContextTemplatesResponse,
)

router = APIRouter(prefix="/api/v2", tags=["context"], dependencies=[Depends(verify_api_key)])

# 内存中的上下文模板存储
templates: dict[str, ContextTemplate] = {}


def _now() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


@router.post("/context-templates", response_model=ContextTemplateResponse, status_code=status.HTTP_200_OK)
async def create_context_template(body: ContextTemplateCreateRequest):
    """创建新的上下文模板。"""
    template_id = str(uuid.uuid4())
    now = _now()
    template = ContextTemplate(
        template_id=template_id,
        name=body.name,
        template=body.template,
        description=body.description,
        created_at=now,
        updated_at=now,
    )
    templates[template_id] = template
    return ContextTemplateResponse(**template.model_dump())


@router.get("/context-templates", response_model=ListContextTemplatesResponse)
async def list_context_templates():
    """列出所有上下文模板。"""
    items = list(templates.values())
    return ListContextTemplatesResponse(
        templates=[ContextTemplateResponse(**t.model_dump()) for t in items],
        total_count=len(items),
        row_count=len(items),
    )


@router.get("/context-templates/{template_id}", response_model=ContextTemplateResponse)
async def get_context_template(template_id: str):
    """获取单个上下文模板。"""
    template = templates.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Context template not found")
    return ContextTemplateResponse(**template.model_dump())


@router.put("/context-templates/{template_id}", response_model=ContextTemplateResponse)
async def update_context_template(template_id: str, body: ContextTemplateUpdateRequest):
    """更新上下文模板。"""
    template = templates.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Context template not found")

    updated = ContextTemplate(
        template_id=template_id,
        name=body.name if body.name is not None else template.name,
        template=body.template if body.template is not None else template.template,
        description=body.description if body.description is not None else template.description,
        created_at=template.created_at,
        updated_at=_now(),
    )
    templates[template_id] = updated
    return ContextTemplateResponse(**updated.model_dump())


@router.delete("/context-templates/{template_id}", status_code=status.HTTP_200_OK)
async def delete_context_template(template_id: str):
    """删除上下文模板。"""
    if template_id not in templates:
        raise HTTPException(status_code=404, detail="Context template not found")
    del templates[template_id]
    return {"message": "Context template deleted", "template_id": template_id}
