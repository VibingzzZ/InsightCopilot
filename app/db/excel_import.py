# Excel 导入器：官方脱敏数据 -> 运行库
#
# 流程（对应数据库设计文档第 6 节）：
#   Excel -> allowlist 字段读取 -> 规范化/类型校验 -> ID 关联
#         -> 敏感字段掩码 -> upsert 核心表 -> 生成 service_event -> 统计
#
# 说明：
# - pandas/openpyxl 仅在脚本运行时懒加载，业务 API 不依赖。
# - 列名映射使用别名表，官方文件列名确认后只需调整 COLUMN_ALIASES。
# - 使用 --inspect 可打印每个 sheet 的实际列名与样例，用于快速校准映射。

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.masking import (
    hash_nickname,
    mask_alipay_account,
    mask_display_name,
    mask_tracking_no,
)
from app.core.time_utils import to_iso, utc_now
from app.models import (
    Consumer,
    Message,
    SalesOrder,
    ServiceEvent,
    ServiceSession,
    ServiceTicket,
)

IMPORT_BATCH_PREFIX = "excel-"

# ---------------------------------------------------------------- 列名别名表

COLUMN_ALIASES: dict[str, list[str]] = {
    # 通用
    "session_id": ["会话ID", "会话id", "session_id", "会话编号", "sessionId"],
    "consumer_nickname": ["客户昵称", "买家昵称", "昵称", "消费者昵称", "nickname", "用户昵称"],
    "store_name": ["店铺名称", "店铺", "store", "门店"],
    "scene_major": ["一级场景", "场景一级", "scene_major", "一级问题"],
    "scene_minor": ["二级场景", "场景二级", "scene_minor", "二级问题"],
    "session_status": ["会话状态", "状态", "session_status"],
    "started_at": ["会话开始时间", "开始时间", "started_at"],
    "ended_at": ["会话结束时间", "结束时间", "ended_at"],
    "message_id": ["消息ID", "消息id", "message_id", "msg_id"],
    "seq_no": ["序号", "seq", "seq_no", "消息序号"],
    "sent_at": ["发送时间", "消息时间", "时间", "sent_at"],
    "role": ["发送方", "角色", "role", "发送角色"],
    "sender_label": ["发送方名称", "发送人", "sender"],
    "content_type": ["消息类型", "内容类型", "content_type"],
    "message_text": ["消息内容", "聊天内容", "内容", "message", "text"],
    "image_path": ["图片", "图片路径", "image_path", "图片地址"],
    "is_target_buyer_message": ["指定买家消息", "目标消息", "is_target_buyer_message"],
    "order_id": ["订单ID", "订单id", "订单号", "order_id", "order_no"],
    "sku": ["SKU", "sku", "商品编码", "货号"],
    "product_name": ["商品名称", "产品名称", "商品", "product_name"],
    "quantity": ["数量", "购买数量", "quantity"],
    "paid_amount": ["实付金额", "支付金额", "金额", "paid_amount", "实付"],
    "order_status": ["订单状态", "order_status"],
    "ordered_at": ["下单时间", "ordered_at", "创建时间"],
    "paid_at": ["付款时间", "支付时间", "paid_at"],
    "shipped_at": ["发货时间", "shipped_at"],
    "carrier": ["快递公司", "物流公司", "carrier", "快递"],
    "tracking_no": ["物流单号", "快递单号", "运单号", "tracking_no", "物流号", "单号"],
    "shipping_province": ["收货省份", "省份", "province", "省"],
    "shipping_city": ["收货城市", "城市", "city", "市"],
    "gift_description": ["赠品", "赠品信息", "gift"],
    "buyer_note": ["买家留言", "买家备注", "备注", "buyer_note"],
    # 工单通用
    "ticket_id": ["工单号", "工单ID", "工单id", "ticket_id", "ticket_no"],
    "ticket_reason": ["工单原因", "问题描述", "原因", "reason"],
    "ticket_priority": ["优先级", "priority"],
    "ticket_status": ["工单状态", "处理状态", "status"],
    "ticket_assignee": ["处理人", "责任人", "负责人", "assignee"],
}

# 工单 sheet 名称 -> ticket_type
TICKET_SHEET_KEYWORDS: list[tuple[str, str]] = [
    ("补发", "replenishment_exchange"),
    ("换货", "replenishment_exchange"),
    ("打款", "offline_payment"),
    ("物流", "logistics"),
    ("不良反应", "adverse_reaction"),
    ("过敏", "adverse_reaction"),
    ("退货", "return"),
]

CHAT_SHEET_KEYWORDS = ("聊天", "消息", "会话记录", "chat", "message")
ORDER_SHEET_KEYWORDS = ("订单", "order")

# 各工单类型允许的 detail 字段别名（白名单，与原值字段隔离）
TICKET_DETAIL_ALIASES: dict[str, dict[str, list[str]]] = {
    "replenishment_exchange": {
        "ship_sku": ["补发SKU", "ship_sku"],
        "ship_product_name": ["补发商品", "ship_product_name"],
        "quantity": ["数量", "quantity"],
        "warehouse": ["仓库", "warehouse"],
        "replacement_tracking_masked": ["补发物流单号", "replacement_tracking"],
        "expedite": ["加急", "expedite"],
    },
    "offline_payment": {
        "payment_type": ["打款类型", "payment_type"],
        "refund_reason_type": ["退款原因类型", "refund_reason_type"],
        "refund_amount_cent": ["打款金额", "退款金额", "refund_amount"],
        "related_tracking_masked": ["关联物流单号", "related_tracking"],
        "transfer_status": ["转账状态", "transfer_status"],
        "alipay_name_masked": ["支付宝实名", "支付宝姓名"],
        "alipay_account_masked": ["支付宝账号"],
    },
    "logistics": {
        "problem_type": ["物流问题类型", "problem_type"],
        "carrier": ["快递公司", "carrier"],
        "package_tracking_masked": ["包裹物流单号", "package_tracking"],
        "warehouse": ["仓库", "warehouse"],
        "solution": ["处理方案", "solution"],
        "abnormal_flag": ["异常标记", "abnormal_flag"],
    },
    "adverse_reaction": {
        "reaction_type": ["反应类型", "reaction_type"],
        "age_band": ["年龄段", "age_band"],
        "skin_type": ["肤质", "skin_type"],
        "product_name": ["产品名称", "product_name"],
        "batch_no_masked": ["批次号", "batch_no"],
        "affected_area": ["使用部位", "affected_area"],
        "symptom_summary": ["症状描述", "症状", "symptom_summary"],
        "onset_after": ["出现时间", "onset_after"],
        "stopped_use": ["是否停用", "stopped_use"],
        "sought_medical_help": ["是否就医", "sought_medical_help"],
        "follow_up_status": ["回访状态", "follow_up_status"],
    },
    "return": {
        "package_type": ["包裹类型", "package_type"],
        "return_reason": ["退货原因", "return_reason"],
        "return_tracking_masked": ["退货物流单号", "return_tracking"],
        "refund_no_masked": ["退款单号", "refund_no"],
        "receipt_advice": ["收货建议", "receipt_advice"],
        "abnormal_flag": ["异常标记", "abnormal_flag"],
    },
}


@dataclass
class ImportStats:
    sessions: int = 0
    messages: int = 0
    orders: int = 0
    tickets: int = 0
    consumers: int = 0
    events: int = 0
    skipped_rows: int = 0
    unlinked_rows: int = 0
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "sessions": self.sessions,
            "messages": self.messages,
            "orders": self.orders,
            "tickets": self.tickets,
            "consumers": self.consumers,
            "events": self.events,
            "skipped_rows": self.skipped_rows,
            "unlinked_rows": self.unlinked_rows,
            "warnings": self.warnings[:20],
        }


def inspect_workbook(path: Path) -> None:
    """打印工作表、列名与样例行，用于校准列名映射。"""
    import pandas as pd

    sheets = pd.read_excel(path, sheet_name=None)
    for name, frame in sheets.items():
        print(f"\n=== Sheet: {name} | 行数: {len(frame)} ===")
        print("列名:", list(frame.columns))
        if len(frame) > 0:
            print("样例:", frame.iloc[0].to_dict())


def import_workbook(path: Path, db: Session) -> ImportStats:
    """读取 Excel 并 upsert 到运行库；调用方负责事务提交。"""
    import pandas as pd

    stats = ImportStats()
    batch_id = f"{IMPORT_BATCH_PREFIX}{utc_now().strftime('%Y%m%d%H%M%S')}"
    sheets = pd.read_excel(path, sheet_name=None)

    chat_frames: list[Any] = []
    order_frames: list[Any] = []
    ticket_frames: list[tuple[str, Any]] = []

    for sheet_name, frame in sheets.items():
        matched_ticket_type = _match_ticket_type(sheet_name)
        if matched_ticket_type:
            ticket_frames.append((matched_ticket_type, frame))
        elif any(key.lower() in sheet_name.lower() for key in CHAT_SHEET_KEYWORDS):
            chat_frames.append(frame)
        elif any(key.lower() in sheet_name.lower() for key in ORDER_SHEET_KEYWORDS):
            order_frames.append(frame)
        else:
            stats.warnings.append(f"未识别的工作表已跳过: {sheet_name}")

    for frame in chat_frames:
        _import_chat(frame, db, batch_id, stats)
    for frame in order_frames:
        _import_orders(frame, db, batch_id, stats)
    for ticket_type, frame in ticket_frames:
        _import_tickets(frame, db, batch_id, stats, ticket_type)

    return stats


# ---------------------------------------------------------------- 各实体导入


def _import_chat(frame: Any, db: Session, batch_id: str, stats: ImportStats) -> None:
    session_cache: dict[str, ServiceSession] = {}
    seq_counter: dict[str, int] = {}

    for _, row in frame.iterrows():
        session_id = _text(_pick(row, "session_id"))
        message_text = _text(_pick(row, "message_text"))
        if not session_id or message_text is None:
            stats.skipped_rows += 1
            continue

        session = session_cache.get(session_id)
        if session is None:
            session = db.scalar(select(ServiceSession).where(ServiceSession.session_id == session_id))
        if session is None:
            nickname = _text(_pick(row, "consumer_nickname")) or ""
            consumer = _upsert_consumer(db, nickname, batch_id)
            session = ServiceSession(
                session_id=session_id,
                consumer_id=consumer.consumer_id,
                store_name=_text(_pick(row, "store_name")),
                scene_major=_text(_pick(row, "scene_major")),
                scene_minor=_text(_pick(row, "scene_minor")),
                status=_map_session_status(_pick(row, "session_status")),
                started_at=_time(_pick(row, "started_at")),
                ended_at=_time(_pick(row, "ended_at")),
                emotion="unknown",
                risk_level="L0",
                source_import_batch=batch_id,
            )
            db.add(session)
            stats.sessions += 1
        session_cache[session_id] = session

        seq_no = int(_pick(row, "seq_no") or 0) or seq_counter.get(session_id, 0) + 1
        seq_counter[session_id] = max(seq_counter.get(session_id, 0), seq_no)

        message_id = _text(_pick(row, "message_id")) or f"{session_id}-m{seq_no}"
        existing = db.scalar(select(Message.message_id).where(Message.message_id == message_id))
        if existing:
            continue
        db.add(
            Message(
                message_id=message_id,
                session_id=session_id,
                seq_no=seq_no,
                sent_at=_time(_pick(row, "sent_at")) or to_iso(utc_now()),
                role=_map_role(_pick(row, "role")),
                sender_label=_text(_pick(row, "sender_label")),
                content_type=_text(_pick(row, "content_type")) or "text",
                message_text=message_text,
                image_path=_text(_pick(row, "image_path")),
                is_target_buyer_message=_bool(_pick(row, "is_target_buyer_message")),
                source_sheet="chat",
            )
        )
        stats.messages += 1
        sent_at = _time(_pick(row, "sent_at"))
        if sent_at and (session.last_message_at is None or sent_at > session.last_message_at):
            session.last_message_at = sent_at


def _import_orders(frame: Any, db: Session, batch_id: str, stats: ImportStats) -> None:
    for _, row in frame.iterrows():
        order_no = _text(_pick(row, "order_id"))
        if not order_no:
            stats.skipped_rows += 1
            continue
        session_id = _text(_pick(row, "session_id"))
        session = (
            db.scalar(select(ServiceSession).where(ServiceSession.session_id == session_id)) if session_id else None
        )
        if session is None:
            stats.unlinked_rows += 1
            continue
        order_id = order_no if order_no.startswith("O") else f"O{order_no}"
        existing = db.scalar(select(SalesOrder).where(SalesOrder.order_id == order_id))
        order = existing or SalesOrder(
            order_id=order_id,
            order_no=order_id,
            consumer_id=session.consumer_id,
            source_import_batch=batch_id,
        )
        order.session_id = session.session_id
        order.store_name = _text(_pick(row, "store_name")) or session.store_name
        order.sku = _text(_pick(row, "sku"))
        order.product_name = _text(_pick(row, "product_name"))
        order.quantity = int(_pick(row, "quantity") or 1)
        amount_cent = _money_to_cent(_pick(row, "paid_amount"))
        order.unit_price_cent = amount_cent
        order.paid_amount_cent = amount_cent
        order.order_status = _text(_pick(row, "order_status")) or "unknown"
        order.ordered_at = _time(_pick(row, "ordered_at"))
        order.paid_at = _time(_pick(row, "paid_at"))
        order.shipped_at = _time(_pick(row, "shipped_at"))
        order.carrier = _text(_pick(row, "carrier"))
        order.tracking_no_masked = mask_tracking_no(_text(_pick(row, "tracking_no")))
        order.shipping_province = _text(_pick(row, "shipping_province"))
        order.shipping_city = _text(_pick(row, "shipping_city"))
        order.gift_description = _text(_pick(row, "gift_description"))
        order.buyer_note_redacted = _text(_pick(row, "buyer_note"))
        if existing is None:
            db.add(order)
            stats.orders += 1


def _import_tickets(frame: Any, db: Session, batch_id: str, stats: ImportStats, ticket_type: str) -> None:
    for _, row in frame.iterrows():
        ticket_no = _text(_pick(row, "ticket_id"))
        session_id = _text(_pick(row, "session_id"))
        if not ticket_no or not session_id:
            stats.skipped_rows += 1
            continue
        session = db.scalar(select(ServiceSession).where(ServiceSession.session_id == session_id))
        if session is None:
            stats.unlinked_rows += 1
            continue
        ticket_id = ticket_no if ticket_no.startswith("T") else f"T{ticket_no}"
        detail = _extract_ticket_detail(row, ticket_type)
        existing = db.scalar(select(ServiceTicket).where(ServiceTicket.ticket_id == ticket_id))
        ticket = existing or ServiceTicket(
            ticket_id=ticket_id,
            ticket_no=ticket_id,
            ticket_type=ticket_type,
            session_id=session_id,
            consumer_id=session.consumer_id,
            source_sheet=ticket_type,
        )
        ticket.order_id = _order_id_of(row, db)
        ticket.reason = _text(_pick(row, "ticket_reason"))
        ticket.priority = _text(_pick(row, "ticket_priority")) or "normal"
        ticket.status = _text(_pick(row, "ticket_status")) or "pending"
        ticket.assignee = _text(_pick(row, "ticket_assignee"))
        ticket.detail_json = json.dumps(detail, ensure_ascii=False)
        if existing is None:
            db.add(ticket)
            stats.tickets += 1
            db.add(
                ServiceEvent(
                    consumer_id=session.consumer_id,
                    session_id=session_id,
                    order_id=ticket.order_id,
                    ticket_id=ticket_id,
                    event_type="ticket_status",
                    occurred_at=to_iso(utc_now()),
                    actor_type="system",
                    title=f"工单导入: {ticket_type}",
                    content=f"工单 {ticket_id} 从官方数据导入。",
                    source_type="ticket",
                    source_id=ticket_id,
                    evidence_message_ids=json.dumps([], ensure_ascii=False),
                )
            )
            stats.events += 1


# ---------------------------------------------------------------- 工具函数


def _upsert_consumer(db: Session, nickname: str, batch_id: str) -> Consumer:
    nickname_hash = hash_nickname(nickname)
    consumer = db.scalar(select(Consumer).where(Consumer.nickname_hash == nickname_hash))
    if consumer:
        return consumer
    consumer = Consumer(
        consumer_id=f"C{nickname_hash[:10].upper()}",
        display_name_masked=mask_display_name(nickname),
        nickname_hash=nickname_hash,
        risk_level="L0",
    )
    db.add(consumer)
    db.flush()
    return consumer


def _pick(row: Any, key: str) -> Any:
    for alias in COLUMN_ALIASES.get(key, []):
        if alias in row.index:
            value = row[alias]
            if value is not None and str(value).strip() not in ("", "nan", "NaT"):
                return value
    return None


def _extract_ticket_detail(row: Any, ticket_type: str) -> dict[str, Any]:
    detail: dict[str, Any] = {}
    for field_name, aliases in TICKET_DETAIL_ALIASES.get(ticket_type, {}).items():
        for alias in aliases:
            if alias in row.index:
                value = row[alias]
                if value is None or str(value).strip() in ("", "nan", "NaT"):
                    continue
                detail[field_name] = _sanitize_detail(field_name, value)
                break
    return detail


def _sanitize_detail(field_name: str, value: Any) -> Any:
    """敏感字段在内存中即完成掩码，原值不落库。"""
    text = _text(value)
    if text is None:
        return None
    if field_name in ("alipay_name_masked", "alipay_account_masked"):
        return mask_alipay_account(text) if "account" in field_name else mask_display_name(text)
    if field_name.endswith("_tracking_masked"):
        return mask_tracking_no(text)
    if field_name.endswith("_amount_cent"):
        return _money_to_cent(value)
    if field_name in ("stopped_use", "sought_medical_help", "expedite", "abnormal_flag"):
        return _bool(value)
    if field_name == "quantity":
        return int(value) if str(value).isdigit() else None
    return text


def _order_id_of(row: Any, db: Session) -> str | None:
    order_no = _text(_pick(row, "order_id"))
    if not order_no:
        return None
    order_id = order_no if order_no.startswith("O") else f"O{order_no}"
    exists = db.scalar(select(SalesOrder.order_id).where(SalesOrder.order_id == order_id))
    return order_id if exists else None


def _match_ticket_type(sheet_name: str) -> str | None:
    for keyword, ticket_type in TICKET_SHEET_KEYWORDS:
        if keyword in sheet_name:
            return ticket_type
    return None


def _map_role(value: Any) -> str:
    text = str(value or "").strip()
    mapping = {
        "买家": "buyer",
        "客户": "buyer",
        "消费者": "buyer",
        "buyer": "buyer",
        "客服": "agent",
        "卖家": "agent",
        "agent": "agent",
        "系统": "system",
        "system": "system",
    }
    return mapping.get(text, "buyer" if "buyer" in text.lower() else "agent")


def _map_session_status(value: Any) -> str:
    text = str(value or "").strip()
    mapping = {
        "进行中": "open",
        "已结束": "closed",
        "已关闭": "closed",
        "待处理": "pending",
        "open": "open",
        "closed": "closed",
        "pending": "pending",
    }
    return mapping.get(text, "open")


def _bool(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "是", "y"}


def _money_to_cent(value: Any) -> int:
    if value is None:
        return 0
    text = str(value).replace("¥", "").replace("元", "").replace(",", "").strip()
    try:
        return int(round(float(text) * 100))
    except ValueError:
        return 0


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in ("", "nan", "NaT", "None"):
        return None
    return text


def _time(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return to_iso(value)
    text = str(value).strip()
    if not text or text in ("nan", "NaT"):
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return to_iso(datetime.strptime(text, fmt))
        except ValueError:
            continue
    return None
