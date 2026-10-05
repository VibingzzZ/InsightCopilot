# 订单路由：订单事实查询与条件检索

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session as DbSession

from app.core.deps import get_db
from app.core.envelope import ok
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("")
def list_orders(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    order_no: str | None = Query(None, max_length=64, description="订单号精确匹配"),
    customer_id: str | None = Query(None, max_length=64, description="按消费者筛选"),
    session_id: str | None = Query(None, max_length=64, description="按关联会话筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """按订单号或关联条件（消费者/会话）检索订单列表。"""
    items, total = order_service.list_orders(
        db, order_no=order_no, customer_id=customer_id, session_id=session_id, page=page, page_size=page_size
    )
    return ok(request, {"items": items}, page=page, page_size=page_size, total=total)


@router.get("/{order_id}")
def get_order(request: Request, order_id: str, db: Annotated[DbSession, Depends(get_db)]) -> dict:
    return ok(request, order_service.get_order(db, order_id))
