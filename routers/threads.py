import json
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from database import get_db
from deps import get_graphiti, verify_api_key
from engine.context_assembly import ContextBlockConfig, assemble_context_block
from engine.graphiti_engine import add_messages_to_graph, clear_session_graph
from models.thread import (
    AddThreadMessagesRequest,
    AddThreadMessagesResponse,
    Message,
    MessageListResponse,
    Thread,
    ThreadContextResponse,
    ThreadCreateRequest,
    ThreadListResponse,
    ThreadSummary,
)

router = APIRouter(prefix="/api/v2/threads", tags=["threads"], dependencies=[Depends(verify_api_key)])

# 为 /api/v2/messages/{message_uuid} 单独准备一个无 prefix 的路由器，
# 因为该端点不属于 /api/v2/threads 前缀。
message_router = APIRouter(prefix="/api/v2", tags=["threads"], dependencies=[Depends(verify_api_key)])


def _row_to_thread(row: aiosqlite.Row) -> Thread:
    """把 sessions 表的一行转换为 Thread 模型。"""
    return Thread(
        uuid=row["session_id"],
        thread_id=row["session_id"],
        user_id=row["user_id"],
        metadata=json.loads(row["metadata"] or "{}"),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _ep_to_message(ep) -> Message:
    """把 Graphiti episode 转换为 Message 模型。"""
    content = ep.content if hasattr(ep, "content") else str(ep)
    parts = content.split(": ", 1)
    role, body = (parts[0], parts[1]) if len(parts) == 2 else ("unknown", content)
    return Message(
        uuid=ep.uuid,
        role=role,
        content=body,
        created_at=ep.created_at if hasattr(ep, "created_at") else None,
        metadata={},
    )


@router.post(
    "",
    response_model=Thread,
    status_code=status.HTTP_200_OK,
)
async def create_thread(
    body: ThreadCreateRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    """创建 Thread；内部复用 sessions 表，thread_id 映射到 session_id。"""
    thread_id = body.thread_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    try:
        await db.execute(
            "INSERT INTO sessions (session_id, user_id, metadata, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (thread_id, body.user_id, json.dumps(body.metadata), now, now),
        )
        await db.commit()
    except aiosqlite.IntegrityError:
        raise HTTPException(status_code=409, detail=f"Thread '{thread_id}' already exists")
    row = await (await db.execute("SELECT * FROM sessions WHERE session_id = ?", (thread_id,))).fetchone()
    return _row_to_thread(row)


@router.get(
    "",
    response_model=ThreadListResponse,
)
async def list_threads(
    page_number: int = 1,
    page_size: int = 100,
    order_by: str = "created_at",
    asc: bool = False,
    db: aiosqlite.Connection = Depends(get_db),
):
    """分页列出所有 Thread。"""
    offset = (page_number - 1) * page_size
    sort_column = order_by if order_by in {"created_at", "updated_at"} else "created_at"
    sort_direction = "ASC" if asc else "DESC"

    rows = await (await db.execute(
        f"SELECT * FROM sessions ORDER BY {sort_column} {sort_direction} LIMIT ? OFFSET ?",
        (page_size, offset),
    )).fetchall()
    count_row = await (await db.execute("SELECT COUNT(*) FROM sessions")).fetchone()
    total = count_row[0] if count_row else 0

    return ThreadListResponse(
        threads=[_row_to_thread(r) for r in rows],
        total_count=total,
        row_count=len(rows),
    )


@router.get(
    "/{thread_id}",
    response_model=Thread,
)
async def get_thread(
    thread_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """获取单个 Thread 详情。"""
    row = await (await db.execute("SELECT * FROM sessions WHERE session_id = ?", (thread_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Thread not found")
    return _row_to_thread(row)


@router.delete(
    "/{thread_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_thread(
    thread_id: str,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
):
    """删除 Thread，同时清空其对应的图记忆。"""
    row = await (await db.execute("SELECT * FROM sessions WHERE session_id = ?", (thread_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Thread not found")

    graphiti = get_graphiti(request)
    await clear_session_graph(graphiti, thread_id)

    await db.execute("DELETE FROM sessions WHERE session_id = ?", (thread_id,))
    await db.commit()
    return {"message": "Thread deleted", "thread_id": thread_id}


@router.get(
    "/{thread_id}/messages",
    response_model=MessageListResponse,
)
async def get_thread_messages(
    thread_id: str,
    request: Request,
    limit: int = 100,
    cursor: int | None = None,
    lastn: int | None = None,
    db: aiosqlite.Connection = Depends(get_db),
):
    """获取 Thread 的消息列表，cursor 仅作兼容性占位。"""
    row = await (await db.execute("SELECT * FROM sessions WHERE session_id = ?", (thread_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Thread not found")

    graphiti = get_graphiti(request)
    n = lastn if lastn is not None else (limit if cursor is None else limit)
    episodes = await graphiti.retrieve_episodes(
        reference_time=datetime.now(timezone.utc),
        last_n=n,
        group_ids=[thread_id],
    )
    messages = [_ep_to_message(ep) for ep in episodes]
    return MessageListResponse(messages=messages, total_count=len(messages), row_count=len(messages))


@router.post(
    "/{thread_id}/messages",
    response_model=AddThreadMessagesResponse,
    status_code=status.HTTP_200_OK,
)
async def add_thread_messages(
    thread_id: str,
    body: AddThreadMessagesRequest,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
):
    """同步向 Thread 追加消息（OpenZep 内部已是异步写入）。"""
    row = await (await db.execute("SELECT * FROM sessions WHERE session_id = ?", (thread_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Thread not found")

    graphiti = get_graphiti(request)
    await add_messages_to_graph(graphiti, thread_id, [m.model_dump() for m in body.messages])
    return AddThreadMessagesResponse(ok=True)


@router.post(
    "/{thread_id}/messages-batch",
    response_model=AddThreadMessagesResponse,
    status_code=status.HTTP_200_OK,
)
async def add_thread_messages_batch(
    thread_id: str,
    body: AddThreadMessagesRequest,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
):
    """批量追加消息，与同步接口行为一致，直接返回确认。"""
    return await add_thread_messages(thread_id, body, request, db)


class _UpdateMessageRequest(BaseModel):
    """更新消息元数据的内部请求体。"""

    metadata: dict[str, Any] = {}


@message_router.patch(
    "/messages/{message_uuid}",
    response_model=Message,
)
async def update_message_metadata(
    message_uuid: str,
    body: _UpdateMessageRequest,
):
    """更新消息元数据；Graphiti 不原生支持消息元数据，返回带有新元数据的 Message。"""
    return Message(
        uuid=message_uuid,
        role="",
        content="",
        metadata=body.metadata,
    )


@router.get(
    "/{thread_id}/summary",
    response_model=ThreadSummary,
)
async def get_thread_summary(
    thread_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """返回 Thread 摘要占位。"""
    row = await (await db.execute("SELECT * FROM sessions WHERE session_id = ?", (thread_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Thread not found")
    return ThreadSummary(
        uuid=thread_id,
        created_at=datetime.fromisoformat(row["created_at"]),
        content="",
    )


@router.get(
    "/{thread_id}/context",
    response_model=ThreadContextResponse,
)
async def get_thread_context(
    thread_id: str,
    request: Request,
    template_id: str | None = None,
    db: aiosqlite.Connection = Depends(get_db),
):
    """基于 Thread 的图记忆组装上下文。"""
    row = await (await db.execute("SELECT * FROM sessions WHERE session_id = ?", (thread_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Thread not found")

    graphiti = get_graphiti(request)
    user_id = row["user_id"] or thread_id
    context_block = await assemble_context_block(
        graphiti=graphiti,
        user_id=user_id,
        group_ids=[thread_id],
        query="",
        config=ContextBlockConfig(),
    )
    # template_id 仅作兼容性占位
    _ = template_id
    return ThreadContextResponse(context=context_block.context, messages=[])
