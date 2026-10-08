# 工单路由：统一核心字段 + 白名单 detail + 字段式更新（PATCH）

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session as DbSession

from app.core.deps import get_db
from app.core.envelope import ok
from app.schemas.api import TicketUpdateRequest
from app.services import ticket_service

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("/{ticket_id}")
def get_ticket(
    request: Request,
    ticket_id: str,
    db: Annotated[DbSession, Depends(get_db)],
    include: str | None = Query(None, description="可选：events"),
) -> dict:
    include_events = bool(include and "events" in {part.strip() for part in include.split(",")})
    return ok(request, ticket_service.get_ticket(db, ticket_id, include_events=include_events))


@router.patch("/{ticket_id}")
def update_ticket(
    request: Request,
    ticket_id: str,
    payload: TicketUpdateRequest,
    db: Annotated[DbSession, Depends(get_db)],
    x_operator_id: str | None = Header(None, alias="X-Operator-ID", description="操作人标识，写入审计事件"),
) -> dict:
    """更新工单状态/优先级/处理人/备注；状态变化自动写入 service_event 审计与时间线。"""
    return ok(request, ticket_service.update_ticket(db, ticket_id, payload=payload, operator_id=x_operator_id))
