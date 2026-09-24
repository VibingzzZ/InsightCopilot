"""核心副驾链路端到端测试。

全部走 mode="mock"：CI 没有 API Key（Key 不该进仓库），而且 Mock 结果可重复，
断言才有意义。真实模型的表现由评测脚本负责，不放在单测里。
"""

import pytest

from app.agent.nodes.fact_check import fact_check_node
from app.agent.run import CASES, _make_state, run_copilot
from app.agent.schemas.contract import CopilotResult, EvidenceRef

# 回复里不允许出现的医疗表述（文档红线：不做诊断、不给用药建议）
FORBIDDEN_IN_REPLY = ("确诊", "病因", "口服", "服用", "抹药", "开药", "抗生素", "药物")


def _run(name: str) -> CopilotResult:
    request = CASES[name]["request"].model_copy(update={"mode": "mock"})
    return run_copilot(request)


def test_refund_case_is_l0_with_evidence():
    result = _run("退款")

    assert result.insight.risk_level == "L0"
    assert result.insight.intent_primary == "订单服务"
    assert result.insight.evidence
    assert result.draft_reply
    assert result.adverse is None


def test_logistics_case():
    result = _run("物流")

    assert result.insight.risk_level == "L0"
    assert result.insight.intent_primary == "物流问题"
    assert result.insight.evidence
    assert result.draft_reply


def test_adverse_case_is_l3():
    result = _run("不良反应")

    assert result.insight.risk_level == "L3"
    assert result.adverse is not None
    assert result.adverse.grade == "L3"
    assert result.adverse.ticket_draft is not None
    assert result.adverse.ticket_draft["priority"] == "critical"
    assert result.draft_reply


def test_adverse_case_does_not_reask_medical_visit():
    """消费者已经说过就医了，不能再问一遍。"""
    result = _run("不良反应")

    assert result.adverse is not None
    assert result.adverse.medical_visit is True
    assert "是否就医" not in result.adverse.missing_fields
    assert "产品批次号" not in result.adverse.missing_fields


def test_adverse_reply_has_no_diagnosis():
    result = _run("不良反应")

    assert result.draft_reply
    for word in FORBIDDEN_IN_REPLY:
        assert word not in result.draft_reply


def test_evidence_is_traceable():
    """高风险结论必须能回溯到具体业务事实。"""
    result = _run("不良反应")

    assert result.insight.evidence
    for item in result.insight.evidence:
        assert item.source_id
        assert item.source_type in {"chat", "order", "ticket", "rule", "action"}


def test_mock_mode_marks_degraded():
    result = _run("退款")

    assert result.insight.degraded is True
    assert result.insight.model_route == "mock"


def test_fact_check_flags_fabricated_amount():
    """草稿里出现证据中没有的金额，必须被标出来。"""
    state = _make_state(CASES["退款"]["request"])
    state["reply_draft"] = "您的 599 元退款已经到账，请查收"
    state["evidence"] = [EvidenceRef(source_type="order", source_id="202509120001", quote="订单状态：已签收")]

    result = fact_check_node(state)

    assert result["fact_check"]["status"] == "needs_review"
    assert any("599" in claim for claim in result["fact_check"]["unverified_claims"])


def test_fact_check_passes_when_claim_is_backed():
    state = _make_state(CASES["物流"]["request"])
    state["reply_draft"] = "您的包裹已发货，物流单号 SF****7890"
    state["evidence"] = [
        EvidenceRef(
            source_type="order",
            source_id="202509150007",
            quote="订单状态：已发货；物流：SF****7890",
        )
    ]

    result = fact_check_node(state)

    assert result["fact_check"]["status"] == "pass"
    assert result["fact_check"]["blocked"] is False


def test_fact_check_blocks_unverified_claim_in_high_risk():
    """L2/L3 场景不允许带未核实的事实发送。"""
    state = _make_state(CASES["不良反应"]["request"])
    state["risk_level"] = "L3"
    state["reply_draft"] = "我们会赔您 500 元"
    state["evidence"] = [EvidenceRef(source_type="order", source_id="202509010033", quote="订单状态：已签收")]

    result = fact_check_node(state)

    assert result["fact_check"]["blocked"] is True


def test_extract_promises_normalizes_due():
    from app.agent.run import extract_promises
    from app.agent.schemas.contract import PromiseExtractRequest

    result = extract_promises(
        PromiseExtractRequest(
            session_id="S-DEMO-001",
            message_id="M-900",
            message_text="明天上午给您安排退款到账",
            mode="mock",
        )
    )

    assert result.candidate is not None
    assert result.candidate.promise_type == "refund"
    assert result.candidate.due_expression == "明天上午"
    # 截止时间必须来自 time.py，而不是模型编的
    assert result.candidate.due_at is not None
    assert result.candidate.due_at.endswith("+08:00")


def test_extract_promises_marks_vague_time_for_confirmation():
    from app.agent.run import extract_promises
    from app.agent.schemas.contract import PromiseExtractRequest

    result = extract_promises(
        PromiseExtractRequest(
            session_id="S-DEMO-001",
            message_id="M-901",
            message_text="我们会尽快给您回访",
            mode="mock",
        )
    )

    assert result.candidate is not None
    assert result.candidate.due_at is None
    assert result.candidate.needs_confirmation is True


@pytest.mark.parametrize("name", list(CASES))
def test_all_cases_produce_reply(name):
    result = _run(name)

    assert result.draft_reply
    assert result.fact_check.status in {"pass", "needs_review"}
