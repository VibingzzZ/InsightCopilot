# 会话路由：队列列表、聚合详情与聊天消息检索
#
# 当前开发阶段已下线：Agent 副驾结论（GET /sessions/{id}/copilot）与 SSE 事件流
# （GET /sessions/{id}/stream），代码迁移至 app/api/routes/deprecated_agent.py 保留。

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session as DbSession

from app.core.deps import get_db
from app.core.envelope import ok
from app.schemas.api import SessionMessageCreateRequest
from app.services import session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
def list_sessions(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, max_length=100, description="脱敏昵称、会话 ID、场景关键词"),
    risk_level: Literal["L0", "L1", "L2", "L3"] | None = Query(None),
    status: Literal["open", "closed", "pending"] | None = Query(None),
    scene_major: str | None = Query(None, max_length=50),
    customer_id: str | None = Query(None, max_length=64, description="按消费者筛选"),
    sort: Literal["last_message_at", "risk"] | None = Query(None, description="默认风险优先视图"),
) -> dict:
    items, total = session_service.list_sessions(
        db,
        q=q,
        risk_level=risk_level,
        status=status,
        scene_major=scene_major,
        customer_id=customer_id,
        sort=sort or "risk",
        page=page,
        page_size=page_size,
    )
    return ok(request, {"items": items}, page=page, page_size=page_size, total=total)


@router.get("/{session_id}")
def get_session_detail(
    request: Request,
    session_id: str,
    db: Annotated[DbSession, Depends(get_db)],
    include: str | None = Query(None, description="可选：events,orders,tickets"),
) -> dict:
    return ok(request, session_service.get_session_detail(db, session_id, include=include))


@router.get("/{session_id}/messages")
def get_session_messages(
    request: Request,
    session_id: str,
    db: Annotated[DbSession, Depends(get_db)],
    order: Literal["asc", "desc"] = Query("asc", description="默认按 seq_no 升序（聊天读取顺序）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict:
    """按会话 ID 分页获取聊天消息记录。"""
    items, total = session_service.list_messages(db, session_id, order=order, page=page, page_size=page_size)
    return ok(request, {"items": items}, page=page, page_size=page_size, total=total)


@router.post("/{session_id}/messages")
def create_session_message(
    request: Request,
    session_id: str,
    payload: SessionMessageCreateRequest,
    db: Annotated[DbSession, Depends(get_db)],
    x_operator_id: str | None = Header(None, alias="X-Operator-ID", description="操作人标识，写入审计事件"),
) -> dict:
    """模拟客服发送消息（send=true）或保存草稿（send=false）。"""
    result = session_service.append_message(
        db, session_id, payload=payload, operator_id=x_operator_id
    )
    return ok(request, result)