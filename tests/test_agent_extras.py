"""补齐后的 Agent 新能力测试：否定语、图片识别、轨迹摘要、成本日志、会话级切分。"""

from app.agent import cost
from app.agent.mock import mock_risk, mock_vision
from app.agent.run import CASES, run_copilot


def test_negation_cancels_symptom():
    assert mock_risk("没有红肿，也没有瘙痒").adverse_reaction is False
    assert mock_risk("我一点也不疼").adverse_reaction is False


def test_positive_symptom_still_hits():
    assert mock_risk("用了之后脸很红很疼").adverse_reaction is True


def test_negation_cancels_medical_visit():
    assert mock_risk("我还没去医院").medical_visit is False
    assert mock_risk("已经去过医院了").medical_visit is True


def test_mock_vision_placeholder_pending():
    result = mock_vision([{"message_text": "[图片]", "content_type": "image"}])
    assert result.clarity == "待识别"
    assert result.image_type == "未知"


def test_mock_vision_with_data_is_clear():
    result = mock_vision(
        [{"message_text": "[图片]", "content_type": "image", "image_b64": "x", "batch_no_masked": "B2409**"}]
    )
    assert result.clarity == "清晰"
    assert result.image_type == "患处照片"


def test_run_copilot_produces_timeline_summary():
    result = run_copilot(CASES["退款"]["request"].model_copy(update={"mode": "mock"}))
    assert result.insight.timeline_summary
    assert "退款" in result.insight.timeline_summary or "承诺" in result.insight.timeline_summary


def test_cost_logs_recorded_in_mock_mode():
    cost.clear_call_logs()
    run_copilot(CASES["退款"]["request"].model_copy(update={"mode": "mock"}))
    logs = cost.get_call_logs()
    assert logs
    assert all(r.degraded for r in logs)
    assert {r.route for r in logs} >= {"fast", "reasoning"}
    # 退款 L0 无图片，不应有 vision 调用
    assert all(r.route != "vision" for r in logs)


def test_cost_session_totals():
    cost.clear_call_logs()
    run_copilot(CASES["退款"]["request"].model_copy(update={"mode": "mock"}))
    totals = cost.session_totals("S-DEMO-001")
    assert totals["calls"] > 0
    assert totals["total_tokens"] == 0  # mock 无 token


def test_adverse_case_runs_vision_and_marks_pending():
    result = run_copilot(CASES["不良反应"]["request"].model_copy(update={"mode": "mock"}))
    assert result.adverse is not None
    assert result.adverse.image_clarity == "待识别"
    assert "图片或门诊资料" in result.adverse.missing_fields
    assert any(item.source_type == "image" for item in result.insight.evidence)


def test_split_by_session_no_leak():
    from scripts.eval_agent import split_by_session

    samples = [
        {"session_id": "A", "message_text": "x"},
        {"session_id": "A", "message_text": "y"},
        {"session_id": "B", "message_text": "z"},
        {"session_id": "C", "message_text": "w"},
    ]
    train, test = split_by_session(samples, test_ratio=0.34, seed=42)
    train_sessions = {s["session_id"] for s in train}
    test_sessions = {s["session_id"] for s in test}
    assert train_sessions.isdisjoint(test_sessions)
    assert test
