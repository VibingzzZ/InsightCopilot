"""Agent 图共享状态。"""

from operator import add, or_
from typing import Annotated, TypedDict

from app.agent.schemas.contract import EvidenceRef


class RiskInfo(TypedDict):
    """Risk Extraction 的结构化输出，由 LLM 提取，Risk Engine 只读它做规则判定。"""

    adverse_reaction: bool
    severity: str  # none / mild / obvious / severe，用于区分 L1 与 L2
    symptoms: list[str]
    medical_visit: bool
    regulatory_complaint: bool  # 监管投诉 / 舆情曝光 / 明确威胁


class FactCheck(TypedDict):
    """Reply 草稿的事实校验结果，由确定性代码产出。"""

    status: str  # pass / needs_review
    unverified_claims: list[str]
    blocked: bool


class CustomerState(TypedDict):
    # 输入层：由 CopilotRequest 预组装，Agent 不查库
    session_id: str
    customer_name_masked: str
    current_message: str
    messages: list[dict]
    orders: list[dict]
    tickets: list[dict]
    promises: list[dict]
    mode: str  # auto / real / mock

    # 理解层
    intent: dict  # {primary, secondary, entities}
    emotion: str
    emotion_trend: str

    # 风险层
    risk: RiskInfo
    risk_level: str  # L0 / L1 / L2 / L3
    risk_reasons: list[str]

    # 数据层：从 orders / tickets 关联出的当前任务相关事实
    linked_order: dict
    linked_tickets: list[dict]

    # 证据层（add reducer：节点只返回新增条目，LangGraph 自动累加）
    evidence: Annotated[list[EvidenceRef], add]

    # 处置层
    missing_fields: list[str]
    suggested_actions: list[str]
    adverse: dict | None

    # 表达层
    reply_draft: str
    fact_check: FactCheck

    # 可观测性：任一节点降级则整体标记降级，所以用 or_ 而不是覆盖
    degraded: Annotated[bool, or_]
    model_route: str
