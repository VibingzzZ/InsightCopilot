# API 序列化层：数据库实体 -> 接口契约字典（统一脱敏与 RFC3339 时间）
#
# 当前阶段已下线：promise_item / copilot_snapshot（承诺与副驾视图，代码保留待恢复）。

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.masking import mask_alipay_account
from app.core.time_utils import seconds_until, to_api_time
from app.models import AIAnalysis, Consumer, Message, Promise, SalesOrder, ServiceEvent, ServiceSession, ServiceTicket
from app.schemas.schemas import (
    AdverseReactionDetail,
    LogisticsDetail,
    OfflinePaymentDetail,
    ReplenishmentExchangeDetail,
    ReturnDetail,
)

TICKET_DETAIL_MODELS: dict[str, type[BaseModel]] = {
    "replenishment_exchange": ReplenishmentExchangeDetail,
    "offline_payment": OfflinePaymentDetail,
    "logistics": LogisticsDetail,
    "adverse_reaction": AdverseReactionDetail,
    "return": ReturnDetail,
}


def money_display(cent: int | None) -> str | None:
    if cent is None:
        return None
    return f"¥{cent / 100:.2f}"


def event_item(event: ServiceEvent) -> dict[str, Any]:
    evidence: list[str] = []
    if event.evidence_message_ids:
        try:
            evidence = json.loads(event.evidence_message_ids)
        except (TypeError, ValueError):
            evidence = []
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "occurred_at": to_api_time(event.occurred_at),
        "title": event.title,
        "content": event.content,
        "source_type": event.source_type,
        "source_id": event.source_id,
        "evidence_message_ids": evidence,
        "actor_type": event.actor_type,
        "actor_id": event.actor_id,
        "ticket_id": event.ticket_id,
        "order_id": event.order_id,
    }


def message_item(message: Message) -> dict[str, Any]:
    return {
        "message_id": message.message_id,
        "session_id": message.session_id,
        "seq_no": message.seq_no,
        "sent_at": to_api_time(message.sent_at),
        "role": message.role,
        "sender_label": message.sender_label,
        "content_type": message.content_type,
        "message_text": message.message_text,
        "image_path": message.image_path,
        "is_target_buyer_message": bool(message.is_target_buyer_message),
    }


def session_brief(session: ServiceSession, consumer: Consumer | None) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "customer_id": session.consumer_id,
        "customer_name_masked": consumer.display_name_masked if consumer else "用户**",
        "store_name": session.store_name,
        "scene_major": session.scene_major,
        "scene_minor": session.scene_minor,
        "status": session.status,
        "started_at": to_api_time(session.started_at),
        "last_message_at": to_api_time(session.last_message_at),
        "intent_primary": session.intent_primary,
        "intent_secondary": session.intent_secondary,
        "emotion": session.emotion,
        "risk_level": session.risk_level,
        "summary": session.summary,
        "unresolved_count": session.unresolved_count,
    }


def order_item(order: SalesOrder, related_ticket_ids: list[str] | None = None) -> dict[str, Any]:
    return {
        "order_id": order.order_id,
        "order_no": order.order_no,
        "session_id": order.session_id,
        "customer_id": order.consumer_id,
        "store_name": order.store_name,
        "sku": order.sku,
        "product_name": order.product_name,
        "quantity": order.quantity,
        "unit_price_cent": order.unit_price_cent,
        "unit_price_display": money_display(order.unit_price_cent),
        "paid_amount_cent": order.paid_amount_cent,
        "paid_amount_display": money_display(order.paid_amount_cent),
        "order_status": order.order_status,
        "ordered_at": to_api_time(order.ordered_at),
        "paid_at": to_api_time(order.paid_at),
        "shipped_at": to_api_time(order.shipped_at),
        "carrier": order.carrier,
        "tracking_no_masked": order.tracking_no_masked,
        "shipping_province": order.shipping_province,
        "shipping_city": order.shipping_city,
        "gift_description": order.gift_description,
        "buyer_note_redacted": order.buyer_note_redacted,
        "related_session_ids": [order.session_id] if order.session_id else [],
        "related_ticket_ids": related_ticket_ids or [],
    }


def ticket_item(ticket: ServiceTicket, events: list[ServiceEvent] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "ticket_id": ticket.ticket_id,
        "ticket_no": ticket.ticket_no,
        "ticket_type": ticket.ticket_type,
        "session_id": ticket.session_id,
        "customer_id": ticket.consumer_id,
        "order_id": ticket.order_id,
        "reason": ticket.reason,
        "priority": ticket.priority,
        "status": ticket.status,
        "assignee": ticket.assignee,
        "detail": sanitize_ticket_detail(ticket.ticket_type, ticket.detail_json),
        "created_at": to_api_time(ticket.created_at),
        "completed_at": to_api_time(ticket.completed_at),
        "updated_at": to_api_time(ticket.updated_at),
    }
    if events is not None:
        item["events"] = [event_item(e) for e in events]
    return item


def sanitize_ticket_detail(ticket_type: str, detail_json: str | None) -> dict[str, Any]:
    """按 ticket_type 白名单校验 detail_json：未知字段丢弃，隐私字段兜底掩码。"""
    parsed: dict[str, Any] = {}
    if detail_json:
        try:
            loaded = json.loads(detail_json)
            if isinstance(loaded, dict):
                parsed = loaded
        except (TypeError, ValueError):
            parsed = {}

    model_cls = TICKET_DETAIL_MODELS.get(ticket_type)
    if model_cls is not None and parsed:
        try:
            validated = model_cls.model_validate(parsed)
            detail = validated.model_dump(exclude_none=True)
        except ValidationError:
            known = set(model_cls.model_fields)
            detail = {k: v for k, v in parsed.items() if k in known}
    else:
        detail = parsed

    for key in ("alipay_name_masked", "alipay_account_masked"):
        if detail.get(key):
            detail[key] = mask_alipay_account(str(detail[key])) if "account" in key else detail[key]
    return detail


def promise_item(
    promise: Promise,
    *,
    session: ServiceSession | None = None,
    consumer: Consumer | None = None,
    now: datetime | None = None,
    include_verification: bool = False,
) -> dict[str, Any]:
    """承诺序列化。【已下线：承诺只读视图暂停输出，恢复时重新接入会话详情】"""
    item: dict[str, Any] = {
        "promise_id": promise.promise_id,
        "session_id": promise.session_id,
        "customer_id": promise.consumer_id,
        "customer_name_masked": consumer.display_name_masked if consumer else None,
        "promise_type": promise.promise_type,
        "statement": promise.statement,
        "due_at": to_api_time(promise.due_at),
        "status": promise.status,
        "remaining_seconds": seconds_until(promise.due_at, now),
        "owner_type": promise.owner_type,
        "owner_id": promise.owner_id,
        "source_message_id": promise.source_message_id,
        "risk_level": session.risk_level if session else None,
        "version": promise.version,
        "evidence": [
            {
                "source_type": "chat",
                "source_id": promise.source_message_id,
                "message_id": promise.source_message_id,
            }
        ],
        "confirmed_at": to_api_time(promise.confirmed_at),
        "fulfilled_at": to_api_time(promise.fulfilled_at),
        "cancelled_at": to_api_time(promise.cancelled_at),
    }
    if include_verification:
        item["verification"] = {
            "verification_type": promise.verification_type,
            "verification_ref": promise.verification_ref,
            "evidence_event_id": promise.evidence_event_id,
        }
    return item


def _load_json_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def copilot_snapshot(analysis: AIAnalysis | None) -> dict[str, Any]:
    """会话详情中的 copilot 快照：读取最近一次分析记录（尚无分析时为 None）。

    intent_json 约定保存完整的结构化结论（意图/风险理由/建议动作）。
    【已下线：Agent 副驾与详情分析段暂停输出，恢复时重新接入会话详情。】
    """
    if analysis is None:
        return {
            "insight": None,
            "draft_reply": None,
            "generated_at": None,
            "analysis_id": None,
            "model_route": None,
            "degraded": False,
        }

    intent_json = _load_json_dict(analysis.intent_json)
    raw_evidence = _load_json_dict_or_list(analysis.evidence_message_ids)
    missing_fields = _load_json_dict_or_list(analysis.missing_fields_json)

    degraded = (analysis.model_route or "mock") == "mock"
    insight = {
        "intent_primary": intent_json.get("intent_primary"),
        "intent_secondary": intent_json.get("intent_secondary"),
        "emotion": analysis.emotion or "unknown",
        "risk_level": analysis.risk_level or "L0",
        "risk_reasons": intent_json.get("risk_reasons") or [],
        "missing_fields": missing_fields if isinstance(missing_fields, list) else [],
        "suggested_actions": intent_json.get("suggested_actions") or [],
        "evidence": [
            {"source_type": "chat", "source_id": str(mid), "message_id": str(mid), "quote": None}
            for mid in (raw_evidence if isinstance(raw_evidence, list) else [])
        ],
        "model_route": analysis.model_route or "mock",
        "degraded": degraded,
    }
    return {
        "insight": insight,
        "draft_reply": analysis.draft_text,
        "generated_at": to_api_time(analysis.created_at),
        "analysis_id": analysis.analysis_id,
        "model_route": analysis.model_route,
        "degraded": degraded,
    }


def _load_json_dict_or_list(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None
