# 客户服务：基础信息与统计查询（会话/订单/工单维度）
#
# - 统计口径与工作台一致：未闭环工单 = status 不在 CLOSED_TICKET_STATUSES。
# - 输出统一走 to_api_time 转换为固定 +08:00 展示时间。

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.core.errors import customer_not_found
from app.core.time_utils import to_api_time
from app.models import Consumer, SalesOrder, ServiceSession, ServiceTicket
from app.services.session_service import CLOSED_TICKET_STATUSES


def get_customer(db: DbSession, customer_id: str) -> dict:
    """客户基础信息与统计；不存在时抛 404 CUSTOMER_NOT_FOUND。"""
    consumer = db.get(Consumer, customer_id)
    if consumer is None:
        raise customer_not_found(customer_id)

    session_count = db.scalar(
        select(func.count()).select_from(ServiceSession).where(ServiceSession.consumer_id == customer_id)
    )
    order_count = db.scalar(select(func.count()).select_from(SalesOrder).where(SalesOrder.consumer_id == customer_id))
    ticket_count = db.scalar(
        select(func.count()).select_from(ServiceTicket).where(ServiceTicket.consumer_id == customer_id)
    )
    open_ticket_count = db.scalar(
        select(func.count())
        .select_from(ServiceTicket)
        .where(ServiceTicket.consumer_id == customer_id, ServiceTicket.status.not_in(CLOSED_TICKET_STATUSES))
    )

    return {
        "customer_id": consumer.consumer_id,
        "display_name_masked": consumer.display_name_masked,
        "risk_level": consumer.risk_level,
        "risk_note": consumer.risk_note,
        "created_at": to_api_time(consumer.created_at),
        "updated_at": to_api_time(consumer.updated_at),
        "statistics": {
            "session_count": int(session_count or 0),
            "order_count": int(order_count or 0),
            "ticket_count": int(ticket_count or 0),
            "open_ticket_count": int(open_ticket_count or 0),
        },
    }
