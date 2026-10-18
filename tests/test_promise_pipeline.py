"""承诺跟踪闭环 + 建单 / 动作确认 / Demo 重置 的回归测试。

对应初赛两条标志性能力之一「服务承诺跟踪」以及接口文档第 7 节：
- 客服最终发送消息才触发承诺抽取（PR-02），草稿不进入承诺；
- 动作 confirm 带幂等键，重复提交返回同一结果；
- demo reset 可恢复固定基线。
"""

from fastapi.testclient import TestClient


def _first_session_id(client: TestClient) -> str:
    resp = client.get("/api/sessions?page_size=1")
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert items, "baseline 应至少灌入一个会话"
    return items[0]["session_id"]


def test_promises_endpoint_returns_baseline(seeded_client: TestClient) -> None:
    resp = seeded_client.get("/api/promises")
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["total"] >= 1
    sample = body["items"][0]
    for key in ("promise_id", "statement", "status", "due_at", "risk_level"):
        assert key in sample


def test_agent_send_message_extracts_promise(seeded_client: TestClient) -> None:
    session_id = _first_session_id(seeded_client)
    payload = {
        "role": "agent",
        "content": "您好，我们会在明天上午10点前为您完成退款核实并回复明确结果。",
        "send": True,
    }
    resp = seeded_client.post(f"/api/sessions/{session_id}/messages", json=payload)
    assert resp.status_code == 200, resp.text
    promise = resp.json()["data"]["promise"]
    assert promise is not None, "最终发送的客服承诺消息应被抽取落库"
    assert promise["status"] == "pending_confirmation"
    assert promise["source_message_id"] == resp.json()["data"]["message_id"]
    # 「明天上午10点」应归一化为次日 10:00，而非默认正午
    assert "T10:00" in promise["due_at"]

    listed = seeded_client.get(f"/api/promises?session_id={session_id}").json()["data"]["items"]
    assert any(p["promise_id"] == promise["promise_id"] for p in listed)


def test_draft_message_does_not_extract_promise(seeded_client: TestClient) -> None:
    """PR-02：草稿（send=False）不得进入正式承诺。"""
    session_id = _first_session_id(seeded_client)
    payload = {
        "role": "agent",
        "content": "您好，我们会在明天上午10点前为您完成退款核实。",
        "send": False,
    }
    resp = seeded_client.post(f"/api/sessions/{session_id}/messages", json=payload)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["promise"] is None


def test_promise_scan_recomputes_status(seeded_client: TestClient) -> None:
    resp = seeded_client.post("/api/promises/scan", json={})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "scanned" in data and "changed" in data


def test_promise_patch_to_fulfilled(seeded_client: TestClient) -> None:
    # 先通过发送承诺消息拿到一条 pending 承诺
    session_id = _first_session_id(seeded_client)
    sent = seeded_client.post(
        f"/api/sessions/{session_id}/messages",
        json={"role": "agent", "content": "我们会在 3 个工作日内回复处理结果。", "send": True},
    ).json()["data"]
    promise_id = sent["promise"]["promise_id"]

    patched = seeded_client.patch(f"/api/promises/{promise_id}", json={"status": "fulfilled"})
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["status"] == "fulfilled"
    assert patched.json()["data"]["fulfilled_at"] is not None


def test_create_ticket(seeded_client: TestClient) -> None:
    session_id = _first_session_id(seeded_client)
    resp = seeded_client.post(
        "/api/tickets",
        json={
            "session_id": session_id,
            "ticket_type": "refund",
            "priority": "urgent",
            "reason": "回归测试建单",
            "draft_payload": {"symptom_summary": "退款核实"},
        },
    )
    assert resp.status_code == 200, resp.text
    ticket = resp.json()["data"]
    assert ticket["ticket_id"]
    assert ticket["ticket_no"]
    assert ticket["status"] == "in_progress"

    fetched = seeded_client.get(f"/api/tickets/{ticket['ticket_id']}?include=events")
    assert fetched.status_code == 200
    assert any(e["event_type"] == "ticket_created" for e in fetched.json()["data"]["events"])


def test_action_preview_and_confirm_idempotent(seeded_client: TestClient) -> None:
    session_id = _first_session_id(seeded_client)
    preview = seeded_client.post(
        "/api/actions/preview",
        json={"session_id": session_id, "action_type": "CREATE_TICKET", "draft_payload": {"ticket_type": "logistics"}},
    )
    assert preview.status_code == 200
    assert "effect" in preview.json()["data"]["preview"]

    body = {
        "action_type": "CREATE_TICKET",
        "idempotency_key": "idem-regression-0001",
        "payload": {"session_id": session_id, "ticket_type": "logistics", "priority": "normal"},
    }
    first = seeded_client.post("/api/actions/confirm", json=body)
    assert first.status_code == 200, first.text
    assert first.json()["data"]["idempotent"] is False
    result_ticket = first.json()["data"]["result_ticket_id"]
    assert result_ticket

    second = seeded_client.post("/api/actions/confirm", json=body)
    assert second.status_code == 200
    assert second.json()["data"]["idempotent"] is True
    assert second.json()["data"]["result_ticket_id"] == result_ticket


def test_demo_reset_restores_baseline(seeded_client: TestClient) -> None:
    resp = seeded_client.post("/api/demo/reset", json={"scenario": "all"})
    assert resp.status_code == 200, resp.text
    counts = resp.json()["data"]["counts"]
    assert counts["promises"] >= 1
    # reset 后承诺数回到基线（演示数据被清理）
    after = seeded_client.get("/api/promises").json()["data"]["total"]
    assert after == counts["promises"]
