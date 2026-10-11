# 消费者时间线服务：跨会话、订单和工单的统一事件视图
#
# - 默认倒序（主管看板），详情页可传 order=asc。
# - from/to 为 RFC3339 字符串；入库为 UTC ISO，可直接按字符串比较。

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.core.time_utils import parse_iso, to_iso
from app.models import ServiceEvent
from app.services import serializers


def get_timeline(
    db: DbSession,
    consumer_id: str,
    *,
    from_time: str | None = None,
    to_time: str | None = None,
    event_type: str | None = None,
    order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    query = select(ServiceEvent).where(ServiceEvent.consumer_id == consumer_id)

    from_dt = parse_iso(from_time)
    if from_dt is not None:
        query = query.where(ServiceEvent.occurred_at >= to_iso(from_dt))
    to_dt = parse_iso(to_time)
    if to_dt is not None:
        query = query.where(ServiceEvent.occurred_at <= to_iso(to_dt))

    if event_type:
        event_types = [part.strip() for part in event_type.split(",") if part.strip()]
        if event_types:
            query = query.where(ServiceEvent.event_type.in_(event_types))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    ordering = ServiceEvent.occurred_at.asc() if order == "asc" else ServiceEvent.occurred_at.desc()
    events = db.scalars(
        query.order_by(ordering, ServiceEvent.event_id.asc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [serializers.event_item(event) for event in events], int(total)
