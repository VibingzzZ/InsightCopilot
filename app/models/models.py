import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Text, Integer, Boolean, ForeignKey, UniqueConstraint, Index
)
from app.core.database import Base

def utc_now():
    return datetime.now(timezone.utc)

def generate_uuid():
    return str(uuid.uuid4())

# 1. 消费者表
class Consumer(Base):
    __tablename__ = "consumer"

    consumer_id = Column(Text, primary_key=True)
    display_name_masked = Column(Text, nullable=False)
    nickname_hash = Column(Text, nullable=False, unique=True)
    risk_level = Column(Text, default="L0", nullable=False)
    risk_note = Column(Text, nullable=True)
    created_at = Column(Text, default=lambda: utc_now().isoformat(), nullable=False)
    updated_at = Column(Text, default=lambda: utc_now().isoformat(), nullable=False)


# 2. 会话表
class ServiceSession(Base):
    __tablename__ = "service_session"

    session_id = Column(Text, primary_key=True)
    consumer_id = Column(Text, ForeignKey("consumer.consumer_id", ondelete="RESTRICT"), nullable=False)
    store_name = Column(Text, nullable=True)
    scene_major = Column(Text, nullable=True)
    scene_minor = Column(Text, nullable=True)
    status = Column(Text, default="open", nullable=False)
    started_at = Column(Text, nullable=True)
    ended_at = Column(Text, nullable=True)
    last_message_at = Column(Text, nullable=True)
    intent_primary = Column(Text, nullable=True)
    intent_secondary = Column(Text, nullable=True)
    emotion = Column(Text, default="unknown", nullable=False)
    risk_level = Column(Text, default="L0", nullable=False)
    summary = Column(Text, nullable=True)
    unresolved_count = Column(Integer, default=0, nullable=False)
    source_import_batch = Column(Text, nullable=True)
    created_at = Column(Text, default=lambda: utc_now().isoformat(), nullable=False)
    updated_at = Column(Text, default=lambda: utc_now().isoformat(), nullable=False)

    __table_args__ = (
        Index("idx_session_status_last_msg", "status", "last_message_at"),
        Index("idx_session_risk_last_msg", "risk_level", "last_message_at"),
        Index("idx_session_consumer_last_msg", "consumer_id", "last_message_at"),
    )


# 3. 消息表
class Message(Base):
    __tablename__ = "message"

    message_id = Column(Text, primary_key=True)
    session_id = Column(Text, ForeignKey("service_session.session_id", ondelete="RESTRICT"), nullable=False)
    seq_no = Column(Integer, nullable=False)
    sent_at = Column(Text, nullable=False)
    role = Column(Text, nullable=False)
    sender_label = Column(Text, nullable=True)
    content_type = Column(Text, default="text", nullable=False)
    message_text = Column(Text, nullable=True)
    chat_content = Column(Text, nullable=True)
    image_path = Column(Text, nullable=True)
    is_target_buyer_message = Column(Boolean, default=False, nullable=False)
    related_order_id = Column(Text, ForeignKey("sales_order.order_id", ondelete="RESTRICT"), nullable=True)
    related_ticket_id = Column(Text, ForeignKey("service_ticket.ticket_id", ondelete="RESTRICT"), nullable=True)
    source_sheet = Column(Text, nullable=True)
    source_row_no = Column(Integer, nullable=True)
    created_at = Column(Text, default=lambda: utc_now().isoformat(), nullable=False)

    __table_args__ = (
        UniqueConstraint("session_id", "seq_no", name="uq_session_seq"),
        Index("idx_msg_session_sent_seq", "session_id", "sent_at", "seq_no"),
        Index("idx_msg_related_order", "related_order_id"),
        Index("idx_msg_related_ticket", "related_ticket_id"),
    )


# 4. 订单表
class SalesOrder(Base):
    __tablename__ = "sales_order"

    order_id = Column(Text, primary_key=True)
    order_no = Column(Text, nullable=False, unique=True)
    session_id = Column(Text, ForeignKey("service_session.session_id", ondelete="RESTRICT"), nullable=True)
    consumer_id = Column(Text, ForeignKey("consumer.consumer_id", ondelete="RESTRICT"), nullable=False)
    store_name = Column(Text, nullable=True)
    sku = Column(Text, nullable=True)
    product_name = Column(Text, nullable=True)
    quantity = Column(Integer, default=1, nullable=False)
    unit_price_cent = Column(Integer, default=0, nullable=False)
    paid_amount_cent = Column(Integer, default=0, nullable=False)
    order_status = Column(Text, default="unknown", nullable=False)
    ordered_at = Column(Text, nullable=True)
    paid_at = Column(Text, nullable=True)
    shipped_at = Column(Text, nullable=True)
    carrier = Column(Text, nullable=True)
    tracking_no_masked = Column(Text, nullable=True)
    shipping_province = Column(Text, nullable=True)
    shipping_city = Column(Text, nullable=True)
    gift_description = Column(Text, nullable=True)
    buyer_note_redacted = Column(Text, nullable=True)
    source_import_batch = Column(Text, nullable=True)
    created_at = Column(Text, default=lambda: utc_now().isoformat(), nullable=False)
    updated_at = Column(Text, default=lambda: utc_now().isoformat(), nullable=False)


# 5. 统一工单表
class ServiceTicket(Base):
    __tablename__ = "service_ticket"

    ticket_id = Column(Text, primary_key=True)
    ticket_no = Column(Text, nullable=False, unique=True)
    ticket_type = Column(Text, nullable=False)
    session_id = Column(Text, ForeignKey("service_session.session_id", ondelete="RESTRICT"), nullable=False)
    consumer_id = Column(Text, ForeignKey("consumer.consumer_id", ondelete="RESTRICT"), nullable=False)
    order_id = Column(Text, ForeignKey("sales_order.order_id", ondelete="RESTRICT"), nullable=True)
    reason = Column(Text, nullable=True)
    priority = Column(Text, default="normal", nullable=False)
    status = Column(Text, default="draft", nullable=False)
    assignee = Column(Text, nullable=True)
    detail_json = Column(Text, nullable=True)
    source_sheet = Column(Text, nullable=True)
    source_row_no = Column(Integer, nullable=True)
    created_at = Column(Text, default=lambda: utc_now().isoformat(), nullable=False)
    completed_at = Column(Text, nullable=True)
    updated_at = Column(Text, default=lambda: utc_now().isoformat(), nullable=False)


# 6. 服务时间线事件表
class ServiceEvent(Base):
    __tablename__ = "service_event"

    event_id = Column(Text, primary_key=True, default=generate_uuid)
    consumer_id = Column(Text, ForeignKey("consumer.consumer_id", ondelete="RESTRICT"), nullable=True)
    session_id = Column(Text, ForeignKey("service_session.session_id", ondelete="RESTRICT"), nullable=False)
    order_id = Column(Text, ForeignKey("sales_order.order_id", ondelete="RESTRICT"), nullable=True)
    ticket_id = Column(Text, ForeignKey("service_ticket.ticket_id", ondelete="RESTRICT"), nullable=True)
    event_type = Column(Text, nullable=False)
    occurred_at = Column(Text, nullable=False)
    actor_type = Column(Text, nullable=False)
    actor_id = Column(Text, nullable=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=True)
    source_type = Column(Text, nullable=True)
    source_id = Column(Text, nullable=True)
    evidence_message_ids = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(Text, default=lambda: utc_now().isoformat(), nullable=False)

    __table_args__ = (
        Index("idx_event_consumer_occ", "consumer_id", "occurred_at"),
        Index("idx_event_session_occ", "session_id", "occurred_at"),
        Index("idx_event_ticket_occ", "ticket_id", "occurred_at"),
    )


# 7. 服务承诺表
class Promise(Base):
    __tablename__ = "promise"

    promise_id = Column(Text, primary_key=True, default=generate_uuid)
    consumer_id = Column(Text, ForeignKey("consumer.consumer_id", ondelete="RESTRICT"), nullable=False)
    session_id = Column(Text, ForeignKey("service_session.session_id", ondelete="RESTRICT"), nullable=False)
    source_message_id = Column(Text, ForeignKey("message.message_id", ondelete="RESTRICT"), nullable=False)
    promise_type = Column(Text, nullable=False)
    statement = Column(Text, nullable=False)
    owner_type = Column(Text, default="agent", nullable=False)
    owner_id = Column(Text, nullable=True)
    due_at = Column(Text, nullable=False)
    timezone = Column(Text, default="Asia/Shanghai", nullable=False)
    status = Column(Text, default="pending_confirmation", nullable=False)
    verification_type = Column(Text, nullable=True)
    verification_ref = Column(Text, nullable=True)
    confirmed_by = Column(Text, nullable=True)
    confirmed_at = Column(Text, nullable=True)
    fulfilled_at = Column(Text, nullable=True)
    cancelled_at = Column(Text, nullable=True)
    evidence_event_id = Column(Text, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(Text, default=lambda: utc_now().isoformat(), nullable=False)
    updated_at = Column(Text, default=lambda: utc_now().isoformat(), nullable=False)


# 8. AI 分析记录表
class AIAnalysis(Base):
    __tablename__ = "ai_analysis"

    analysis_id = Column(Text, primary_key=True, default=generate_uuid)
    session_id = Column(Text, ForeignKey("service_session.session_id", ondelete="RESTRICT"), nullable=False)
    message_id = Column(Text, ForeignKey("message.message_id", ondelete="RESTRICT"), nullable=True)
    model_route = Column(Text, nullable=False)
    intent_json = Column(Text, nullable=True)
    emotion = Column(Text, nullable=True)
    risk_level = Column(Text, nullable=True)
    missing_fields_json = Column(Text, nullable=True)
    evidence_message_ids = Column(Text, nullable=True)
    draft_text = Column(Text, nullable=True)
    provider_status = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    token_usage_json = Column(Text, nullable=True)
    created_at = Column(Text, default=lambda: utc_now().isoformat(), nullable=False)


# 9. 动作执行表（防重幂等）
class ActionExecution(Base):
    __tablename__ = "action_execution"

    action_id = Column(Text, primary_key=True, default=generate_uuid)
    action_type = Column(Text, nullable=False)
    session_id = Column(Text, ForeignKey("service_session.session_id", ondelete="RESTRICT"), nullable=False)
    operator_id = Column(Text, nullable=False)
    idempotency_key = Column(Text, nullable=False, unique=True)
    preview_json = Column(Text, nullable=True)
    confirmed_payload_json = Column(Text, nullable=True)
    status = Column(Text, default="preview", nullable=False)
    result_ticket_id = Column(Text, nullable=True)
    result_promise_id = Column(Text, nullable=True)
    request_id = Column(Text, nullable=False)
    created_at = Column(Text, default=lambda: utc_now().isoformat(), nullable=False)
    confirmed_at = Column(Text, nullable=True)
    executed_at = Column(Text, nullable=True)


# 10. 不可变审计日志表
class AuditLog(Base):
    __tablename__ = "audit_log"

    audit_id = Column(Text, primary_key=True, default=generate_uuid)
    request_id = Column(Text, nullable=False)
    operator_id = Column(Text, nullable=False)
    action_id = Column(Text, nullable=True)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(Text, nullable=False)
    operation = Column(Text, nullable=False)
    before_json = Column(Text, nullable=True)
    after_json = Column(Text, nullable=True)
    created_at = Column(Text, default=lambda: utc_now().isoformat(), nullable=False)