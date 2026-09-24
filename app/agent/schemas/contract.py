"""Agent 层对外 I/O 契约。

这是前后端与 Agent 之间唯一的接口定义来源：
- 后端按 CopilotRequest 预组装上下文（Agent 不查库、不调外部接口）
- 后端把 CopilotResult 直接映射成接口文档的 CopilotInsight / promise candidate
- 前端按同一份字段渲染右侧插件

字段命名对齐《知微客服副驾 FastAPI 接口设计文档》第 3、7 节。
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["L0", "L1", "L2", "L3"]
AdverseGrade = Literal["L1", "L2", "L3"]  # L0 不进不良反应专项
ModelRoute = Literal["fast", "reasoning", "vision", "mock"]
AgentMode = Literal["auto", "real", "mock"]
SourceType = Literal["chat", "order", "ticket", "rule", "action"]
PromiseType = Literal["refund", "follow_up", "replenishment", "logistics", "other"]
OwnerType = Literal["store", "agent", "team", "system"]


class EvidenceRef(BaseModel):
    """所有 Agent 结论的证据入口。高风险提示必须能回溯到这里。"""

    source_type: SourceType
    source_id: str
    message_id: str | None = None
    quote: str | None = None  # 脱敏短引文


class CopilotRequest(BaseModel):
    """一次副驾请求。业务事实由后端查好传入，Agent 只做语义与结构化。"""

    session_id: str
    current_message: str
    customer_name_masked: str | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    orders: list[dict[str, Any]] = Field(default_factory=list)
    tickets: list[dict[str, Any]] = Field(default_factory=list)
    promises: list[dict[str, Any]] = Field(default_factory=list)
    mode: AgentMode = "auto"


class CopilotInsight(BaseModel):
    """会话洞察：判断层 + 证据层，对应接口文档 CopilotInsight。"""

    intent_primary: str | None = None
    intent_secondary: str | None = None
    entities: list[str] = Field(default_factory=list)
    emotion: str = "unknown"
    emotion_trend: str = "flat"
    risk_level: RiskLevel = "L0"
    risk_reasons: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    model_route: ModelRoute = "mock"
    degraded: bool = False


class AdverseAssessment(BaseModel):
    """不良反应专项评估。

    只做服务风险分级和流程辅助：不做医学诊断，不根据图片判断疾病，
    不替代医生建议。
    """

    grade: AdverseGrade
    symptom_summary: str = ""
    medical_visit: bool = False
    stopped_use: bool | None = None
    missing_fields: list[str] = Field(default_factory=list)
    ticket_draft: dict[str, Any] | None = None  # CREATE_TICKET 的 draft_payload
    safe_reply: str | None = None
    suggested_actions: list[str] = Field(default_factory=list)


class FactCheckResult(BaseModel):
    """回复草稿的事实校验结果。未命中证据的事实断言一律进 needs_review。"""

    status: Literal["pass", "needs_review"] = "pass"
    unverified_claims: list[str] = Field(default_factory=list)
    blocked: bool = False


class CopilotResult(BaseModel):
    """一次副驾分析的完整产出。不改变任何业务状态。"""

    session_id: str
    insight: CopilotInsight
    draft_reply: str | None = None
    adverse: AdverseAssessment | None = None
    fact_check: FactCheckResult = Field(default_factory=FactCheckResult)


class PromiseExtractRequest(BaseModel):
    """承诺抽取入参。只对客服最终发送的消息生效，草稿不进入。"""

    session_id: str
    message_id: str
    message_text: str
    mode: AgentMode = "auto"


class PromiseCandidate(BaseModel):
    """承诺候选。只能由人工确认后生效，Agent 不自动建立承诺。"""

    promise_type: PromiseType = "other"
    statement: str
    due_expression: str | None = None  # 模型识别出的原始时间表达
    due_at: str | None = None  # 确定性时间服务归一化结果，模糊表达为 None
    owner_type: OwnerType = "agent"
    confidence: float = 0.0
    needs_confirmation: bool = False
    evidence: list[EvidenceRef] = Field(default_factory=list)


class PromiseExtractResult(BaseModel):
    """承诺抽取出参，对齐接口文档 POST /api/promises/extract 的响应结构。"""

    candidate: PromiseCandidate | None = None
    needs_confirmation: bool = False
    model_route: ModelRoute = "mock"
    degraded: bool = False
