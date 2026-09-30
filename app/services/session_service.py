# 会话服务：队列查询、聚合详情与聊天消息检索
#
# - 队列排序：默认风险优先（L3/L2 在前），其次按最近消息倒序。
# - 详情聚合消息、订单、工单与事件；输出统一走序列化层脱敏。
# - 当前阶段已下线：承诺只读视图与 Agent 分析快照（代码保留，见文件末尾说明）。

import uuid
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session as DbSession

from app.models import Message, ServiceEvent   # 已有 ServiceSession 就合并
from app.core.time_utils import to_api_time    # to_iso / utc_now 已在
from app.core.time_utils import to_iso, utc_now
from app.schemas.api import SessionMessageCreateRequest
from app.core.errors import session_not_found
from app.models import (
    AIAnalysis,
    Consumer,
    Message,
    Promise,
    SalesOrder,
    ServiceEvent,
    ServiceSession,
    ServiceTicket,
)
from app.services import serializers

# 未完成状态集合（计数与筛选口径）
CLOSED_TICKET_STATUSES = ("completed", "cancelled")
# 承诺未完成状态：当前阶段已下线（保留口径，恢复承诺只读视图时重新启用）
OPEN_PROMISE_STATUSES = ("pending_confirmation", "active", "due_soon", "overdue")

_RISK_CASE = case({"L3": 0, "L2": 1, "L1": 2, "L0": 3}, value=ServiceSession.risk_level, else_=4)


def list_sessions(
    db: DbSession,
    *,
    q: str | None = None,
    risk_level: str | None = None,
    status: str | None = None,
    scene_major: str | None = None,
    customer_id: str | None = None,
    sort: str = "risk",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    base = select(ServiceSession, Consumer).join(Consumer, Consumer.consumer_id == ServiceSession.consumer_id)
    if q:
        like = f"%{q}%"
        base = base.where(
            or_(
                ServiceSession.session_id.like(like),
                Consumer.display_name_masked.like(like),
                ServiceSession.scene_major.like(like),
                ServiceSession.scene_minor.like(like),
            )
        )
    if risk_level:
        base = base.where(ServiceSession.risk_level == risk_level)
    if status:
        base = base.where(ServiceSession.status == status)
    if scene_major:
        base = base.where(ServiceSession.scene_major == scene_major)
    if customer_id:
        base = base.where(ServiceSession.consumer_id == customer_id)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    if sort == "last_message_at":
        order_by = (ServiceSession.last_message_at.desc(), ServiceSession.session_id.desc())
    else:  # risk：工作台默认视图，L3/L2 置顶
        order_by = (_RISK_CASE.asc(), ServiceSession.last_message_at.desc(), ServiceSession.session_id.desc())

    rows = db.execute(base.order_by(*order_by).offset((page - 1) * page_size).limit(page_size)).all()
    return _build_list_items(db, rows), int(total)


def _build_list_items(db: DbSession, rows) -> list[dict]:
    if not rows:
        return []
    # 统计口径为消费者维度：历史会话的未闭环工单需要在新进线时提示
    consumer_ids = sorted({session.consumer_id for session, _ in rows})

    open_ticket_counts = dict(
        db.execute(
            select(ServiceTicket.consumer_id, func.count())
            .where(
                ServiceTicket.consumer_id.in_(consumer_ids),
                ServiceTicket.status.not_in(CLOSED_TICKET_STATUSES),
            )
            .group_by(ServiceTicket.consumer_id)
        ).all()
    )

    items: list[dict] = []
    for session, consumer in rows:
        item = serializers.session_brief(session, consumer)
        item["open_ticket_count"] = int(open_ticket_counts.get(session.consumer_id, 0))
        items.append(item)
    return items


def get_session_detail(db: DbSession, session_id: str, *, include: str | None = None) -> dict:
    """聚合会话详情；include 给定时仅额外返回所列分组（events/orders/tickets）。"""
    session = db.get(ServiceSession, session_id)
    if session is None:
        raise session_not_found(session_id)
    consumer = db.get(Consumer, session.consumer_id)

    sections = {part.strip() for part in include.split(",") if part.strip()} if include else None

    def wanted(name: str) -> bool:
        return sections is None or name in sections

    session_view = serializers.session_brief(session, consumer)
    session_view["open_ticket_count"] = _count_open_tickets(db, session.consumer_id)

    messages = db.scalars(
        select(Message).where(Message.session_id == session_id).order_by(Message.seq_no.asc(), Message.sent_at.asc())
    ).all()

    detail: dict = {
        "session": session_view,
        "messages": [serializers.message_item(message) for message in messages],
    }

    if wanted("orders"):
        # 跨会话轨迹：订单事实可能登记在消费者其他会话（如历史会话创建、本次进线催办）
        orders = db.scalars(
            select(SalesOrder)
            .where(SalesOrder.consumer_id == session.consumer_id)
            .order_by(SalesOrder.ordered_at.asc(), SalesOrder.created_at.asc())
        ).all()
        order_ids = [order.order_id for order in orders]
        ticket_ids_by_order: dict[str, list[str]] = {}
        if order_ids:
            for ticket in db.scalars(select(ServiceTicket).where(ServiceTicket.order_id.in_(order_ids))):
                ticket_ids_by_order.setdefault(ticket.order_id or "", []).append(ticket.ticket_id)
        detail["orders"] = [
            serializers.order_item(order, ticket_ids_by_order.get(order.order_id, [])) for order in orders
        ]
    else:
        detail["orders"] = []

    if wanted("tickets"):
        # 跨会话轨迹：退款/补发工单可能登记在历史会话
        tickets = db.scalars(
            select(ServiceTicket)
            .where(ServiceTicket.consumer_id == session.consumer_id)
            .order_by(ServiceTicket.created_at.asc())
        ).all()
        detail["tickets"] = [serializers.ticket_item(ticket) for ticket in tickets]
    else:
        detail["tickets"] = []

    if wanted("events"):
        events = db.scalars(
            select(ServiceEvent).where(ServiceEvent.session_id == session_id).order_by(ServiceEvent.occurred_at.asc())
        ).all()
        detail["events"] = [serializers.event_item(event) for event in events]
    else:
        detail["events"] = []

    return detail


def list_messages(
    db: DbSession,
    session_id: str,
    *,
    order: str = "asc",
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    """按会话 ID 分页检索聊天消息记录（默认 seq_no 升序，即聊天读取顺序）。"""
    if db.get(ServiceSession, session_id) is None:
        raise session_not_found(session_id)

    query = select(Message).where(Message.session_id == session_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    if order == "asc":
        ordering = (Message.seq_no.asc(), Message.sent_at.asc())
    else:
        ordering = (Message.seq_no.desc(), Message.sent_at.desc())
    messages = db.scalars(query.order_by(*ordering).offset((page - 1) * page_size).limit(page_size)).all()
    return [serializers.message_item(message) for message in messages], int(total)

def append_message(
    db: DbSession,
    session_id: str,
    *,
    payload: SessionMessageCreateRequest,
    operator_id: str | None = None,
) -> dict:
    """追加一条会话消息。

    - send=True：写入 message + service_event，刷新 session.last_message_at
    - send=False：仅写入 message（草稿），不写事件、不刷新会话时间
    返回 message_id / event_id / session_id / seq_no / sent_at。
    """
    session = db.get(ServiceSession, session_id)
    if session is None:
        raise session_not_found(session_id)

    now_iso = to_iso(utc_now())
    next_seq = (
        db.scalar(
            select(func.coalesce(func.max(Message.seq_no), 0)).where(Message.session_id == session_id)
        )
        or 0
    ) + 1

    message_id = f"m-{uuid.uuid4().hex[:12]}"
    message = Message(
        message_id=message_id,
        session_id=session_id,
        seq_no=next_seq,
        sent_at=now_iso,
        role=payload.role,
        sender_label=payload.sender_label or ("客服" if payload.role == "agent" else None),
        content_type="text",
        message_text=payload.content,
        is_target_buyer_message=False,
    )
    db.add(message)

    event_id: str | None = None
    if payload.send:
        event_id = f"e-{uuid.uuid4().hex[:12]}"
        db.add(
            ServiceEvent(
                event_id=event_id,
                consumer_id=session.consumer_id,
                session_id=session_id,
                event_type="message_sent" if payload.role == "agent" else "message_received",
                occurred_at=now_iso,
                actor_type="operator" if payload.role == "agent" else "system",
                actor_id=operator_id,
                title="客服发送消息" if payload.role == "agent" else "系统消息",
                content=payload.content,
                source_type="chat",
                source_id=message_id,
                evidence_message_ids=None,
                metadata_json=None,
            )
        )
        session.last_message_at = now_iso

    db.commit()
    db.refresh(message)

    return {
        "message_id": message_id,
        "event_id": event_id,
        "session_id": session_id,
        "seq_no": next_seq,
        "sent_at": to_api_time(now_iso),
        "send": payload.send,
        "promise_extract_job_id": None,  # 承诺抽取链路暂未接入
    }






# ---------- 以下为已下线能力（承诺只读视图 / Agent 分析快照），代码保留待恢复 ----------


def latest_analysis(db: DbSession, session_id: str) -> AIAnalysis | None:
    """最近一次 Agent 分析记录。【已下线：仅 Agent 副驾/详情分析段使用】"""
    return db.scalars(
        select(AIAnalysis).where(AIAnalysis.session_id == session_id).order_by(AIAnalysis.created_at.desc()).limit(1)
    ).first()


def _count_open_tickets(db: DbSession, consumer_id: str) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(ServiceTicket)
            .where(ServiceTicket.consumer_id == consumer_id, ServiceTicket.status.not_in(CLOSED_TICKET_STATUSES))
        )
        or 0
    )


def _count_active_promises(db: DbSession, consumer_id: str) -> int:
    """未完成承诺计数。【已下线：承诺只读视图暂停输出，恢复时重新接入会话详情】"""
    return int(
        db.scalar(
            select(func.count())
            .select_from(Promise)
            .where(Promise.consumer_id == consumer_id, Promise.status.in_(OPEN_PROMISE_STATUSES))
        )
        or 0
    )
