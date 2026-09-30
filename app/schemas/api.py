# 接口契约模型（对应《FastAPI 接口设计文档》第 3 节）
#
# 字段可扩展，不可删除或改变语义。工单 detail 白名单见 app/schemas/schemas.py。
# 当前阶段启用：TicketUpdateRequest（工单字段式更新）；
# CopilotInsight / Action* / Promise* / MessagePost / PromiseScan / DemoReset 为后续阶段契约（未挂载路由）。

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["L0", "L1", "L2", "L3"]
PromiseStatus = Literal["pending_confirmation", "active", "due_soon", "overdue", "fulfilled", "changed", "cancelled"]
ActionType = Literal["CREATE_TICKET", "ESCALATE", "FOLLOW_UP", "NUDGE_TICKET", "CREATE_PROMISE", "MARK_FULFILLED"]
# 工单状态与优先级枚举（对应数据库设计文档：service_ticket.status / priority）
TicketStatus = Literal["draft", "pending", "in_progress", "pending_customer", "completed", "cancelled"]
TicketPriority = Literal["normal", "urgent", "critical"]


class SessionListItem(BaseModel):
    session_id: str
    customer_id: str
    customer_name_masked: str
    store_name: str
    scene_major: str | None = None
    scene_minor: str | None = None
    last_message_at: datetime | None = None
    risk_level: RiskLevel = "L0"
    emotion: str = "unknown"
    unresolved_count: int = 0
    open_ticket_count: int = 0
    active_promise_count: int = 0


class EvidenceRef(BaseModel):
    source_type: Literal["chat", "order", "ticket", "rule", "action"]
    source_id: str
    message_id: str | None = None
    quote: str | None = None  # 脱敏短引文


class CopilotInsight(BaseModel):
    intent_primary: str | None = None
    intent_secondary: str | None = None
    emotion: str = "unknown"
    risk_level: RiskLevel = "L0"
    risk_reasons: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    model_route: Literal["fast", "reasoning", "vision", "mock"] = "mock"
    degraded: bool = False


class ActionPreviewRequest(BaseModel):
    session_id: str
    action_type: ActionType
    draft_payload: dict[str, Any] = Field(default_factory=dict)
    source_message_id: str | None = None


class ActionConfirmRequest(BaseModel):
    action_id: str
    idempotency_key: str = Field(min_length=8, max_length=128)
    payload: dict[str, Any] | None = None


class PromisePatch(BaseModel):
    status: PromiseStatus | None = None
    due_at: datetime | None = None
    owner_id: str | None = None
    verification_type: str | None = None
    verification_ref: str | None = None
    reason: str | None = None


class PromiseExtractRequest(BaseModel):
    session_id: str
    message_id: str
    message_text: str
    mode: Literal["model", "mock", "auto"] = "auto"


class MessagePostRequest(BaseModel):
    """模拟客服最终发送消息或追加系统消息（send=false 仅草稿，不落库）。"""

    role: Literal["agent", "system"] = "agent"
    content: str = Field(min_length=1, max_length=4000)
    send: bool = True
    client_message_id: str | None = None


class PromiseScanRequest(BaseModel):
    now: datetime | None = None  # 仅 Mock/测试环境允许
    dry_run: bool = False


class DemoResetRequest(BaseModel):
    scenario: Literal["all", "refund", "adverse_reaction", "gift_resend"] = "all"
    seed: str = "baseline-v1"
    preserve_import: bool = True


class TicketUpdateRequest(BaseModel):
    """工单字段式更新（PATCH /api/tickets/{ticket_id}）：至少提供一个字段。

    - status 变更时自动维护 completed_at，并写入 service_event 审计与时间线；
    - note 仅作为审计事件备注，不落库到工单主表。
    """

    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assignee: str | None = Field(None, max_length=64)
    note: str | None = Field(None, max_length=500)

class SessionMessageCreateRequest(BaseModel):
    """模拟客服发送消息 / 保存草稿。"""

    role: Literal["agent", "system", "customer"] = "agent"
    content: str = Field(min_length=1, max_length=5000)
    send: bool = True  # 是否立即发送（否则仅保存草稿）
    client_message_id: str | None = Field(default=None, max_length=64)
    sender_label: str | None = Field(default=None, max_length=50)
