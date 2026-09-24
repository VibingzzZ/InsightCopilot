"""风险分级规则测试（L0-L3 四档边界）。

risk_engine 是纯规则节点，不依赖模型，所以这些断言可以完全确定。
"""

import pytest

from app.agent.nodes.risk_engine import risk_engine_node
from app.agent.state import CustomerState


def _risk(**overrides):
    risk = {
        "adverse_reaction": False,
        "severity": "none",
        "symptoms": [],
        "medical_visit": False,
        "regulatory_complaint": False,
    }
    risk.update(overrides)
    return risk


def _state(risk: dict, emotion: str = "平静") -> CustomerState:
    return {"risk": risk, "emotion": emotion}  # type: ignore[typeddict-item]


@pytest.mark.parametrize(
    ("risk", "emotion", "reason"),
    [
        (_risk(adverse_reaction=True, symptoms=["红肿"], medical_visit=True), "焦虑", "消费者已就医"),
        (_risk(regulatory_complaint=True), "愤怒", "提及监管投诉或舆情曝光"),
        (_risk(adverse_reaction=True, severity="severe", symptoms=["呼吸困难"]), "平静", "症状较严重"),
    ],
)
def test_l3_triggers(risk, emotion, reason):
    result = risk_engine_node(_state(risk, emotion))

    assert result["risk_level"] == "L3"
    assert reason in result["risk_reasons"]


def test_severe_symptom_keyword_alone_is_l3():
    result = risk_engine_node(_state(_risk(severity="severe", symptoms=["眼部肿胀"])))

    assert result["risk_level"] == "L3"


def test_obvious_severity_is_l2():
    result = risk_engine_node(_state(_risk(adverse_reaction=True, severity="obvious", symptoms=["红肿"])))

    assert result["risk_level"] == "L2"
    assert result["risk_reasons"] == ["症状明显（范围扩大或持续加重）"]


def test_adverse_with_strong_emotion_is_l2():
    result = risk_engine_node(_state(_risk(adverse_reaction=True, severity="mild", symptoms=["泛红"]), "愤怒"))

    assert result["risk_level"] == "L2"


def test_mild_adverse_is_l1():
    result = risk_engine_node(_state(_risk(adverse_reaction=True, severity="mild", symptoms=["泛红"])))

    assert result["risk_level"] == "L1"
    assert result["risk_reasons"] == ["出现轻微不良反应，尚未加重"]


def test_emotion_alone_does_not_escalate():
    """单纯情绪不满只记情绪，不单独升级 —— 避免客服告警疲劳。"""
    result = risk_engine_node(_state(_risk(), "愤怒"))

    assert result["risk_level"] == "L0"
    assert result["risk_reasons"] == []


def test_plain_inquiry_is_l0():
    result = risk_engine_node(_state(_risk()))

    assert result["risk_level"] == "L0"
