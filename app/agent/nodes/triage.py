"""合并理解节点：一次模型调用同时产出 intent + emotion + risk（降本）。

原 `intent` / `emotion` / `risk_extraction` 三个节点各自调用一次模型，但三者
输入都只有当前消息。这里合并为一次调用：每次分析少 2 次模型调用，并少两遍
重复的 prompt 头部 + 消息体，直接降低 token 成本。输出的 state 字段与原三节点
完全一致（intent / emotion / emotion_trend / risk），下游 risk_engine 等无需改动。
"""

from app.agent.llm import format_instructions, run_structured
from app.agent.mock import mock_emotion, mock_intent, mock_risk
from app.agent.schemas.analysis import TriageAnalysis
from app.agent.state import CustomerState
from app.prompt.triage import TRIAGE_PROMPT


def _mock_triage(message: str) -> TriageAnalysis:
    """离线 / 降级时的确定性兜底：复用原有三条规则型 mock，不额外调用模型。"""
    intent = mock_intent(message)
    emotion = mock_emotion(message)
    risk = mock_risk(message)
    return TriageAnalysis(
        intent_primary=intent.intent_primary,
        intent_secondary=intent.intent_secondary,
        entities=intent.entities,
        emotion=emotion.emotion,
        emotion_trend=emotion.trend,
        adverse_reaction=risk.adverse_reaction,
        severity=risk.severity,
        symptoms=risk.symptoms,
        medical_visit=risk.medical_visit,
        regulatory_complaint=risk.regulatory_complaint,
    )


def triage_node(state: CustomerState) -> dict:
    prompt = TRIAGE_PROMPT.format(
        message=state["current_message"],
        format_instructions=format_instructions(TriageAnalysis),
    )

    result, degraded = run_structured(
        prompt=prompt,
        schema=TriageAnalysis,
        route="fast",
        mode=state.get("mode", "auto"),
        fallback=lambda: _mock_triage(state["current_message"]),
        session_id=state.get("session_id"),
    )

    return {
        "intent": {
            "primary": result.intent_primary,
            "secondary": result.intent_secondary,
            "entities": result.entities,
        },
        "emotion": result.emotion,
        "emotion_trend": result.emotion_trend,
        "risk": {
            "adverse_reaction": result.adverse_reaction,
            "severity": result.severity,
            "symptoms": result.symptoms,
            "medical_visit": result.medical_visit,
            "regulatory_complaint": result.regulatory_complaint,
        },
        "degraded": degraded,
    }
