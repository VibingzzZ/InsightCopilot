"""风险提取节点。

只负责提取事实（是否不良反应、程度、是否就医、是否监管投诉），
**不下风险等级** —— 等级由 risk_engine 的确定性规则判定。
"""

from app.agent.llm import format_instructions, run_structured
from app.agent.mock import mock_risk
from app.agent.schemas.analysis import RiskExtraction
from app.agent.state import CustomerState
from app.prompt.risk import RISK_EXTRACTION_PROMPT


def risk_extraction_node(state: CustomerState) -> dict:
    prompt = RISK_EXTRACTION_PROMPT.format(
        message=state["current_message"],
        format_instructions=format_instructions(RiskExtraction),
    )

    result, degraded = run_structured(
        prompt=prompt,
        schema=RiskExtraction,
        route="reasoning",
        mode=state.get("mode", "auto"),
        fallback=lambda: mock_risk(state["current_message"]),
    )

    return {"risk": result.model_dump(), "degraded": degraded}
