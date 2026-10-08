# 消费者路由：基础信息查询与跨会话/订单/工单的统一时间线

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session as DbSession

from app.core.deps import get_db
from app.core.envelope import ok
from app.services import consumer_service, timeline_service

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("/{customer_id}")
def get_customer(request: Request, customer_id: str, db: Annotated[DbSession, Depends(get_db)]) -> dict:
    """客户基础信息与统计（会话数、订单数、工单数、未闭环工单数）。"""
    return ok(request, consumer_service.get_customer(db, customer_id))


@router.get("/{customer_id}/timeline")
def get_timeline(
    request: Request,
    customer_id: str,
    db: Annotated[DbSession, Depends(get_db)],
    from_time: str | None = Query(None, alias="from", description="RFC3339 起始时间"),
    to_time: str | None = Query(None, alias="to", description="RFC3339 结束时间"),
    event_type: str | None = Query(None, max_length=200, description="事件类型，逗号分隔多值"),
    order: Literal["asc", "desc"] = Query("desc", description="默认倒序（主管看板）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    items, total = timeline_service.get_timeline(
        db,
        customer_id,
        from_time=from_time,
        to_time=to_time,
        event_type=event_type,
        order=order,
        page=page,
        page_size=page_size,
    )
    return ok(request, {"items": items}, page=page, page_size=page_size, total=total)
