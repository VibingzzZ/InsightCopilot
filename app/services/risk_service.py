# 风险队列服务：会话、工单与承诺的主管视角聚合
#
# 【当前阶段已下线】路由未挂载（见 app/api/routes/risk.py）；代码保留待恢复。
# - 风险理由优先复用最近一次 Agent 分析结论（与副驾卡一致）；
#   尚无分析记录时用规则引擎实时兜底，保证开箱即用。
# - 按 session_id 批量聚合子查询，避免逐会话 N+1。

import json
from collections import defaultdict
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session as DbSession

from app.agents import rules
from app.core.masking import mask_quote
from app.core.time_utils import utc_now
from app.models import AIAnalysis, Consumer, Message, Promise, SalesOrder, ServiceSession, ServiceTicket
from app.services import serializers

CLOSED_TICKET_STATUSES = ("completed", "cancelled")
OPEN_PROMISE_STATUSES = ("pending_confirmation", "active", "due_soon", "overdue")

_RISK_CASE = case({"L3": 0, "L2": 1, "L1": 2, "L0": 3}, value=ServiceSession.risk_level, else_=4)


def build_risk_queue(
    db: DbSession,
    *,
    risk_level: str | None = None,
    ticket_type: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    base = select(ServiceSession, Consumer).join(Consumer, Consumer.consumer_id == ServiceSession.consumer_id)
    if risk_level:
        base = base.where(ServiceSession.risk_level == risk_level)
    if status:
        base = base.where(ServiceSession.status == status)
    if ticket_type:
        # 消费者维度：退款/补发工单可能登记在历史会话，本次进线也需提示
        base = base.where(
            ServiceSession.consumer_id.in_(
                select(ServiceTicket.consumer_id).where(ServiceTicket.ticket_type == ticket_type)
            )
        )

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(
        base.order_by(_RISK_CASE.asc(), ServiceSession.last_message_at.desc(), ServiceSession.session_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    if not rows:
        return [], int(total)

    session_ids = [session.session_id for session, _ in rows]
    consumer_ids = sorted({session.consumer_id for session, _ in rows})

    # 工单/承诺按消费者维度聚合：主管队列需要看到跨会话的未闭环事项
    tickets_by_consumer: dict[str, list[ServiceTicket]] = defaultdict(list)
    for ticket in db.scalars(select(ServiceTicket).where(ServiceTicket.consumer_id.in_(consumer_ids))):
        tickets_by_consumer[ticket.consumer_id].append(ticket)

    promises_by_consumer: dict[str, list[Promise]] = defaultdict(list)
    for promise in db.scalars(select(Promise).where(Promise.consumer_id.in_(consumer_ids))):
        promises_by_consumer[promise.consumer_id].append(promise)

    orders_by_session: dict[str, list[SalesOrder]] = defaultdict(list)
    for order in db.scalars(select(SalesOrder).where(SalesOrder.session_id.in_(session_ids))):
        orders_by_session[order.session_id].append(order)

    messages_by_session: dict[str, list[Message]] = defaultdict(list)
    messages_by_id: dict[str, Message] = {}
    for message in db.scalars(
        select(Message).where(Message.session_id.in_(session_ids)).order_by(Message.sent_at.asc(), Message.seq_no.asc())
    ):
        messages_by_session[message.session_id].append(message)
        messages_by_id[message.message_id] = message

    analyses: dict[str, AIAnalysis] = {}
    for analysis in db.scalars(
        select(AIAnalysis).where(AIAnalysis.session_id.in_(session_ids)).order_by(AIAnalysis.created_at.asc())
    ):
        analyses[analysis.session_id] = analysis  # 升序遍历，最终保留最新一条

    consumer_session_counts = dict(
        db.execute(
            select(ServiceSession.consumer_id, func.count())
            .where(ServiceSession.consumer_id.in_(consumer_ids))
            .group_by(ServiceSession.consumer_id)
        ).all()
    )

    now = utc_now()
    items = [
        _build_item(
            session=session,
            consumer=consumer,
            tickets=tickets_by_consumer.get(session.consumer_id, []),
            promises=promises_by_consumer.get(session.consumer_id, []),
            orders=orders_by_session.get(session.session_id, []),
            messages=messages_by_session.get(session.session_id, []),
            messages_by_id=messages_by_id,
            analysis=analyses.get(session.session_id),
            consumer_session_count=int(consumer_session_counts.get(session.consumer_id, 1)),
            now=now,
        )
        for session, consumer in rows
    ]
    return items, int(total)


def _build_item(
    *,
    session: ServiceSession,
    consumer: Consumer,
    tickets: list[ServiceTicket],
    promises: list[Promise],
    orders: list[SalesOrder],
    messages: list[Message],
    messages_by_id: dict[str, Message],
    analysis: AIAnalysis | None,
    consumer_session_count: int,
    now: datetime,
) -> dict:
    reasons, evidence_ids = _resolve_reasons(
        session=session,
        analysis=analysis,
        messages=messages,
        orders=orders,
        tickets=tickets,
        promises=promises,
        consumer_session_count=consumer_session_count,
        now=now,
    )
    open_tickets = [ticket for ticket in tickets if ticket.status not in CLOSED_TICKET_STATUSES]
    active_promises = [promise for promise in promises if promise.status in OPEN_PROMISE_STATUSES]

    item = serializers.session_brief(session, consumer)
    item.update(
        {
            "risk_reasons": reasons,
            "evidence": _evidence_refs(evidence_ids, messages_by_id),
            "open_ticket_count": len(open_tickets),
            "active_promise_count": len(active_promises),
            "tickets": [
                {
                    "ticket_id": ticket.ticket_id,
                    "ticket_type": ticket.ticket_type,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "reason": ticket.reason,
                }
                for ticket in sorted(tickets, key=lambda t: (t.status in CLOSED_TICKET_STATUSES, t.created_at or ""))
            ],
            "promises": [
                serializers.promise_item(
                    promise, session=session, consumer=consumer, now=now, include_verification=True
                )
                for promise in sorted(active_promises, key=lambda p: p.due_at or "")
            ],
        }
    )
    return item


def _resolve_reasons(
    *,
    session: ServiceSession,
    analysis: AIAnalysis | None,
    messages: list[Message],
    orders: list[SalesOrder],
    tickets: list[ServiceTicket],
    promises: list[Promise],
    consumer_session_count: int,
    now: datetime,
) -> tuple[list[str], list[str]]:
    """优先复用 Agent 结论；无分析记录时由规则引擎实时兜底。"""
    if analysis is not None:
        parsed = _load_json_dict(analysis.intent_json)
        reasons = [str(reason) for reason in (parsed.get("risk_reasons") or [])]
        if reasons:
            evidence = _load_json_list(analysis.evidence_message_ids)
            return reasons, evidence

    result = rules.analyze(
        session=session,
        messages=messages,
        orders=orders,
        tickets=[
            rules.TicketContext(
                ticket_id=ticket.ticket_id,
                ticket_type=ticket.ticket_type,
                status=ticket.status,
                priority=ticket.priority,
            )
            for ticket in tickets
        ],
        promises=[
            rules.PromiseContext(
                promise_id=promise.promise_id,
                session_id=promise.session_id,
                status=promise.status,
                statement=promise.statement,
                promise_type=promise.promise_type,
                due_at=promise.due_at,
                verification_type=promise.verification_type,
                verification_ref=promise.verification_ref,
            )
            for promise in promises
        ],
        consumer_session_count=consumer_session_count,
        now=now,
    )
    return result.risk_reasons, result.evidence_message_ids


def _evidence_refs(evidence_ids: list[str], messages_by_id: dict[str, Message]) -> list[dict]:
    """证据引用：message_id + 脱敏短引文。"""
    refs: list[dict] = []
    for message_id in evidence_ids[:5]:
        message = messages_by_id.get(message_id)
        refs.append(
            {
                "source_type": "chat",
                "source_id": message_id,
                "message_id": message_id,
                "quote": mask_quote(message.message_text if message is not None else None),
            }
        )
    return refs


def _load_json_dict(value: str | None) -> dict:
    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _load_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except (TypeError, ValueError):
        return []
    return [str(item) for item in loaded] if isinstance(loaded, list) else []
