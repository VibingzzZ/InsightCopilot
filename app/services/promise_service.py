# 承诺服务：从客服最终消息抽取承诺、列表查询、状态流转与到期扫描
#
# 设计要点（对应接口文档第 7 节与赛题「服务承诺跟踪」）：
# - 只有客服「最终发送」的消息才进入正式承诺（PR-02），草稿不生效；
# - 模型只读懂「承诺了什么、时间原话是什么」，due_at 一律由 time.py 归一化；
# - 模糊时间（尽快/稍后）不虚构截止时间，落 pending_confirmation 待人工确认；
# - 扫描只针对未完成状态重算 due_soon / overdue，不改变已履约/取消等终态。

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.agent.nodes.promise import extract_promise_candidate
from app.agent.schemas.contract import (
    AgentMode,
)
from app.agent.schemas.contract import (
    PromiseExtractRequest as ContractPromiseExtractRequest,
)
from app.core.errors import ApiError, ErrorCode
from app.core.time_utils import parse_iso, to_iso, utc_now
from app.models import Consumer, Message, Promise, ServiceEvent, ServiceSession
from app.services import serializers

_OPEN_STATUSES = ("pending_confirmation", "active", "due_soon", "overdue")
_DUE_SOON_THRESHOLD_SECONDS = 24 * 3600
_TZ = "Asia/Shanghai"


def _mode_to_contract(mode: str) -> AgentMode:
    """接口层 mode（model/mock/auto）映射到 Agent 契约的 AgentMode。"""
    if mode == "model":
        return "real"
    if mode == "mock":
        return "mock"
    return "auto"


def create_promise_from_message(
    db: DbSession,
    *,
    session_id: str,
    message_id: str,
    text: str,
    mode: str = "auto",
) -> dict | None:
    """从一条客服已发送消息抽取承诺并落库。

    无承诺则返回 None；有承诺则返回序列化后的承诺对象（status=pending_confirmation）。
    同时写入 service_event，保证承诺可回溯到对应聊天消息。
    """
    message = db.get(Message, message_id)
    if message is None or message.session_id != session_id:
        return None
    session = db.get(ServiceSession, session_id)
    if session is None:
        return None
    consumer = db.get(Consumer, session.consumer_id)
    if consumer is None:
        return None

    result = extract_promise_candidate(
        ContractPromiseExtractRequest(
            session_id=session_id,
            message_id=message_id,
            message_text=text,
            mode=_mode_to_contract(mode),
        )
    )
    candidate = result.candidate
    if candidate is None:
        return None

    now = utc_now()
    # 模糊表达（尽快/稍后）不虚构截止时间：用当前时间占位，靠 pending_confirmation 提示人工补时间
    due_at = candidate.due_at or to_iso(now)

    promise = Promise(
        consumer_id=consumer.consumer_id,
        session_id=session_id,
        source_message_id=message_id,
        promise_type=candidate.promise_type,
        statement=candidate.statement,
        owner_type=candidate.owner_type,
        due_at=due_at,
        status="pending_confirmation",
        timezone=_TZ,
        version=1,
    )
    db.add(promise)
    db.flush()

    db.add(
        ServiceEvent(
            consumer_id=consumer.consumer_id,
            session_id=session_id,
            event_type="promise_created",
            occurred_at=to_iso(now),
            actor_type="agent",
            actor_id=None,
            title="识别到一条服务承诺（待确认）",
            content=candidate.statement,
            source_type="chat",
            source_id=message_id,
        )
    )
    db.commit()
    db.refresh(promise)
    return serializers.promise_item(promise, session=session, consumer=consumer)


def list_promises(
    db: DbSession,
    *,
    status: str | None = None,
    session_id: str | None = None,
    consumer_id: str | None = None,
    risk_level: str | None = None,
    due_before: str | None = None,
    overdue_only: bool = False,
    limit: int = 200,
) -> list[dict]:
    """查询承诺队列，支持多维筛选。返回按 due_at 升序的序列化列表。"""
    query = select(Promise)
    if status:
        query = query.where(Promise.status == status)
    if session_id:
        query = query.where(Promise.session_id == session_id)
    if consumer_id:
        query = query.where(Promise.consumer_id == consumer_id)
    if overdue_only:
        query = query.where(Promise.status == "overdue")
    if due_before:
        due = parse_iso(due_before)
        if due is not None:
            query = query.where(Promise.due_at <= to_iso(due))

    rows = db.execute(query.order_by(Promise.due_at.asc()).limit(limit)).scalars().all()
    out: list[dict] = []
    for p in rows:
        session = db.get(ServiceSession, p.session_id)
        consumer = db.get(Consumer, p.consumer_id)
        out.append(serializers.promise_item(p, session=session, consumer=consumer))

    if risk_level:
        out = [item for item in out if item.get("risk_level") == risk_level]
    return out


def patch_promise(db: DbSession, promise_id: str, patch: object, operator_id: str | None = None) -> dict:
    """状态流转与字段更新。

    - pending_confirmation → active（客服确认）
    - active/due_soon/overdue → fulfilled / changed / cancelled
    - 终态（fulfilled/cancelled）自动维护时间戳
    """
    promise = db.get(Promise, promise_id)
    if promise is None:
        raise ApiError(404, ErrorCode.NOT_FOUND, f"承诺不存在：{promise_id}")

    now = utc_now()
    # patch 是 pydantic 模型，直接读字段；用 getattr 兼容 dict 传入
    status = getattr(patch, "status", None)
    due_at = getattr(patch, "due_at", None)
    owner_id = getattr(patch, "owner_id", None)
    verification_type = getattr(patch, "verification_type", None)
    verification_ref = getattr(patch, "verification_ref", None)

    if status is not None:
        promise.status = status
        if status == "fulfilled":
            promise.fulfilled_at = to_iso(now)
        elif status == "cancelled":
            promise.cancelled_at = to_iso(now)
    if due_at is not None:
        parsed = parse_iso(due_at)
        promise.due_at = to_iso(parsed) if parsed is not None else to_iso(now)
    if owner_id is not None:
        promise.owner_id = owner_id
    if verification_type is not None:
        promise.verification_type = verification_type
    if verification_ref is not None:
        promise.verification_ref = verification_ref
    promise.updated_at = to_iso(now)

    db.commit()
    db.refresh(promise)
    session = db.get(ServiceSession, promise.session_id)
    consumer = db.get(Consumer, promise.consumer_id)
    return serializers.promise_item(promise, session=session, consumer=consumer)


def scan_promises(db: DbSession, now: datetime | None = None) -> dict:
    """重算未完成承诺的 due_soon / overdue（不依赖真实等待，可即时模拟扫描）。"""
    now = now or utc_now()
    rows = db.execute(select(Promise).where(Promise.status.in_(_OPEN_STATUSES))).scalars().all()
    changed = 0
    for p in rows:
        due = parse_iso(p.due_at)
        if due is None:
            continue
        remaining = (due - now).total_seconds()
        if remaining < 0:
            new_status = "overdue"
        elif remaining <= _DUE_SOON_THRESHOLD_SECONDS:
            new_status = "due_soon"
        else:
            new_status = "active"
        if new_status != p.status:
            p.status = new_status
            changed += 1
    db.commit()
    return {"scanned": len(rows), "changed": changed}
