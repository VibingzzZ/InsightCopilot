# 订单服务：订单事实查询与条件检索（金额与状态来自数据库，不经过模型改写）

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.core.errors import order_not_found
from app.models import SalesOrder, ServiceTicket
from app.services import serializers


def get_order(db: DbSession, order_id: str) -> dict:
    order = db.get(SalesOrder, order_id)
    if order is None:
        raise order_not_found(order_id)
    ticket_ids = db.scalars(select(ServiceTicket.ticket_id).where(ServiceTicket.order_id == order_id)).all()
    return serializers.order_item(order, list(ticket_ids))


def list_orders(
    db: DbSession,
    *,
    order_no: str | None = None,
    customer_id: str | None = None,
    session_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """按订单号（精确）或关联条件（消费者/会话）检索订单列表，按下单时间倒序。"""
    query = select(SalesOrder)
    if order_no:
        query = query.where(SalesOrder.order_no == order_no)
    if customer_id:
        query = query.where(SalesOrder.consumer_id == customer_id)
    if session_id:
        query = query.where(SalesOrder.session_id == session_id)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    orders = db.scalars(
        query.order_by(SalesOrder.ordered_at.desc(), SalesOrder.order_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    order_ids = [order.order_id for order in orders]
    ticket_ids_by_order: dict[str, list[str]] = {}
    if order_ids:
        for ticket in db.scalars(select(ServiceTicket).where(ServiceTicket.order_id.in_(order_ids))):
            ticket_ids_by_order.setdefault(ticket.order_id or "", []).append(ticket.ticket_id)
    return [serializers.order_item(order, ticket_ids_by_order.get(order.order_id, [])) for order in orders], int(total)
