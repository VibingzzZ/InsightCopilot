# 工单服务：统一核心字段 + 按 ticket_type 白名单校验后的 detail + 字段式更新（PATCH）

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.errors import ApiError, ErrorCode, ticket_not_found
from app.core.time_utils import to_iso, utc_now
from app.models import ServiceEvent, ServiceTicket
from app.schemas.api import TicketUpdateRequest
from app.services import serializers


def get_ticket(db: DbSession, ticket_id: str, *, include_events: bool = False) -> dict:
    ticket = db.get(ServiceTicket, ticket_id)
    if ticket is None:
        raise ticket_not_found(ticket_id)

    events = None
    if include_events:
        events = list(
            db.scalars(
                select(ServiceEvent).where(ServiceEvent.ticket_id == ticket_id).order_by(ServiceEvent.occurred_at.asc())
            ).all()
        )
    return serializers.ticket_item(ticket, events)


def update_ticket(
    db: DbSession,
    ticket_id: str,
    *,
    payload: TicketUpdateRequest,
    operator_id: str | None = None,
) -> dict:
    """字段式更新工单状态/优先级/处理人；变更写入 service_event 审计与时间线。

    - 全部字段为空 -> 400 INVALID_PARAMETER；
    - 传入值与当前一致且无备注 -> 幂等返回，不写事件也不刷新 updated_at；
    - 状态迁移到 completed 时记录 completed_at，从 completed 迁出时清空。
    """
    ticket = db.get(ServiceTicket, ticket_id)
    if ticket is None:
        raise ticket_not_found(ticket_id)

    if all(field is None for field in (payload.status, payload.priority, payload.assignee, payload.note)):
        raise ApiError(400, ErrorCode.INVALID_PARAMETER, "至少提供一个待更新字段（status/priority/assignee/note）")

    changes: dict[str, dict[str, Any]] = {}
    if payload.status is not None and payload.status != ticket.status:
        changes["status"] = {"from": ticket.status, "to": payload.status}
        ticket.status = payload.status
        if payload.status == "completed":
            ticket.completed_at = to_iso(utc_now())
        elif ticket.completed_at:
            ticket.completed_at = None
    if payload.priority is not None and payload.priority != ticket.priority:
        changes["priority"] = {"from": ticket.priority, "to": payload.priority}
        ticket.priority = payload.priority
    if payload.assignee is not None and payload.assignee != ticket.assignee:
        changes["assignee"] = {"from": ticket.assignee, "to": payload.assignee}
        ticket.assignee = payload.assignee

    if not changes and not payload.note:
        return serializers.ticket_item(ticket)

    now_iso = to_iso(utc_now())
    ticket.updated_at = now_iso

    status_change = changes.get("status")
    if status_change:
        title = f"工单状态更新：{status_change['from']} → {status_change['to']}"
    else:
        title = "工单信息更新"
    db.add(
        ServiceEvent(
            consumer_id=ticket.consumer_id,
            session_id=ticket.session_id,
            ticket_id=ticket.ticket_id,
            order_id=ticket.order_id,
            event_type="ticket_status" if status_change else "ticket_update",
            occurred_at=now_iso,
            actor_type="operator",
            actor_id=operator_id,
            title=title,
            content=payload.note,
            source_type="ticket",
            source_id=ticket.ticket_id,
            metadata_json=json.dumps(changes, ensure_ascii=False) if changes else None,
        )
    )
    db.commit()
    db.refresh(ticket)
    return serializers.ticket_item(ticket)
