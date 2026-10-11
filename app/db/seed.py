# 基线灌库与 Demo 重置（事务内完成，失败整笔回滚）
#
# reset_demo 行为（对应数据库设计文档第 7 节）：
# 1. 清理演示运行数据：动作、分析、承诺、事件、审计。
# 2. 清理演示期间生成的业务数据（无导入批次标记的会话/消息/订单/工单/消费者）。
# 3. preserve_import=false 时同时清理 Excel 导入数据（source_import_batch 前缀 excel-）。
# 4. 恢复 baseline-v1 固定初始状态，最后写入 demo_reset 审计记录。

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.time_utils import to_iso, utc_now
from app.db.baseline_data import BASELINE_SEED, SCENARIO_SESSION_IDS, build_baseline
from app.models import (
    ActionExecution,
    AIAnalysis,
    AuditLog,
    Consumer,
    Message,
    Promise,
    SalesOrder,
    ServiceEvent,
    ServiceSession,
    ServiceTicket,
)


def apply_baseline(db: Session, scenario: str = "all", now: datetime | None = None) -> dict[str, int]:
    """将 baseline-v1 数据 upsert 到数据库（不做清理，供脚本初始化使用）。"""
    data = build_baseline(now or utc_now())
    refreshed_at = to_iso(utc_now())

    # 注意：SQLite 外键立即校验，按依赖顺序 flush 保证父行先落库
    for item in data.consumers:
        db.merge(
            Consumer(
                consumer_id=item["consumer_id"],
                display_name_masked=item["display_name_masked"],
                nickname_hash=_nickname_hash(item["consumer_id"]),
                risk_level=item["risk_level"],
                risk_note=item["risk_note"],
                updated_at=refreshed_at,
            )
        )
    db.flush()
    for item in data.sessions:
        db.merge(ServiceSession(**item, source_import_batch=BASELINE_SEED, updated_at=refreshed_at))
    db.flush()
    for item in data.orders:
        db.merge(SalesOrder(**item, source_import_batch=BASELINE_SEED, updated_at=refreshed_at))
    for item in data.tickets:
        db.merge(_ticket_from_item(item, refreshed_at))
    db.flush()
    for item in data.messages:
        db.merge(Message(**item, source_sheet=BASELINE_SEED))
    for item in data.promises:
        db.merge(_promise_from_item(item, refreshed_at))
    db.flush()
    for item in data.events:
        db.merge(_event_from_item(item))

    db.flush()
    return _counts(db)


def reset_demo(
    db: Session,
    scenario: str = "all",
    preserve_import: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    """恢复固定初始数据；在调用方事务中执行，异常时由调用方回滚。"""
    started = utc_now()

    # 1. 演示运行数据整表清理（这些表全部由 Demo 流程生成）
    db.execute(delete(ActionExecution))
    db.execute(delete(AIAnalysis))
    db.execute(delete(Promise))
    db.execute(delete(ServiceEvent))
    db.execute(delete(AuditLog))

    # 2. 演示期间生成的业务行（无来源标记）一律清理：
    #    例如会话中追加的消息、通过动作创建的工单
    db.execute(delete(Message).where(Message.source_sheet.is_(None)))
    db.execute(delete(ServiceTicket).where(ServiceTicket.source_sheet.is_(None)))

    # 3. 业务表：清理演示期间生成的会话（无导入批次标记）
    _cleanup_sessions(db, batch_is_null=True)
    if not preserve_import:
        # 同时清理 Excel 导入数据（source_import_batch 前缀 excel-）
        _cleanup_sessions(db, batch_is_null=False)

    # 4. 恢复基线
    counts = apply_baseline(db, scenario=scenario, now=now)

    # 5. 审计记录
    elapsed_ms = int((utc_now() - started).total_seconds() * 1000)
    db.add(
        AuditLog(
            request_id=f"demo_reset_{started.isoformat()}",
            operator_id="system",
            entity_type="demo",
            entity_id=BASELINE_SEED,
            operation="demo_reset",
            before_json=None,
            after_json=json.dumps(
                {"scenario": scenario, "counts": counts, "duration_ms": elapsed_ms},
                ensure_ascii=False,
            ),
        )
    )
    db.flush()
    return {"counts": counts, "duration_ms": elapsed_ms, "started_at": started}


def _cleanup_sessions(db: Session, batch_is_null: bool) -> None:
    """清理指定批次的会话及其业务数据与会话专属消费者。"""
    if batch_is_null:
        condition = ServiceSession.source_import_batch.is_(None)
    else:
        condition = ServiceSession.source_import_batch.like("excel-%")

    session_ids = db.scalars(select(ServiceSession.session_id).where(condition)).all()
    if not session_ids:
        return
    consumer_ids = db.scalars(
        select(ServiceSession.consumer_id).where(ServiceSession.session_id.in_(session_ids)).distinct()
    ).all()
    db.execute(delete(Message).where(Message.session_id.in_(session_ids)))
    db.execute(delete(SalesOrder).where(SalesOrder.session_id.in_(session_ids)))
    db.execute(delete(ServiceTicket).where(ServiceTicket.session_id.in_(session_ids)))
    db.execute(delete(ServiceSession).where(ServiceSession.session_id.in_(session_ids)))
    for consumer_id in consumer_ids:
        remaining = db.scalar(
            select(ServiceSession.session_id).where(ServiceSession.consumer_id == consumer_id).limit(1)
        )
        if remaining is None:
            db.execute(delete(Consumer).where(Consumer.consumer_id == consumer_id))


def scenario_session_ids(scenario: str) -> list[str]:
    if scenario == "all":
        ids: list[str] = []
        for session_ids in SCENARIO_SESSION_IDS.values():
            ids.extend(session_ids)
        return ids
    return SCENARIO_SESSION_IDS.get(scenario, [])


def _nickname_hash(consumer_id: str) -> str:
    from app.core.masking import hash_nickname

    return hash_nickname(f"baseline::{consumer_id}")


def _ticket_from_item(item: dict[str, Any], refreshed_at: str) -> ServiceTicket:
    payload = dict(item)
    detail = payload.pop("detail", {}) or {}
    payload.setdefault("source_sheet", BASELINE_SEED)
    return ServiceTicket(**payload, detail_json=json.dumps(detail, ensure_ascii=False), updated_at=refreshed_at)


def _promise_from_item(item: dict[str, Any], refreshed_at: str) -> Promise:
    payload = dict(item)
    for key in ("confirmed_at", "fulfilled_at", "cancelled_at"):
        if key in payload and payload[key] is None:
            payload.pop(key)
    payload["updated_at"] = refreshed_at
    return Promise(**payload)


def _event_from_item(item: dict[str, Any]) -> ServiceEvent:
    payload = dict(item)
    evidence = payload.pop("evidence_message_ids", []) or []
    metadata = payload.pop("metadata_json", None)
    # 事件使用确定性 ID，保证重复灌库幂等
    stable_key = (
        f"{payload.get('consumer_id')}|{payload.get('session_id')}|{payload.get('title')}|{payload.get('occurred_at')}"
    )
    payload["event_id"] = "evt-base-" + hashlib.sha1(stable_key.encode("utf-8")).hexdigest()[:16]
    return ServiceEvent(
        **payload,
        evidence_message_ids=json.dumps(evidence, ensure_ascii=False),
        metadata_json=metadata,
    )


def _counts(db: Session) -> dict[str, int]:
    def count(model: Any) -> int:
        return int(db.scalar(select(func.count()).select_from(model)) or 0)

    return {
        "consumers": count(Consumer),
        "sessions": count(ServiceSession),
        "messages": count(Message),
        "orders": count(SalesOrder),
        "tickets": count(ServiceTicket),
        "promises": count(Promise),
        "events": count(ServiceEvent),
    }
