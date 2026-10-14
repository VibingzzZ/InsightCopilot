"""实时通道与测试接口的集成测试。

覆盖六项任务的关键行为：
  - /health 向后兼容
  - POST /api/test/buyer_message 返回分析结果并广播（Task 04/05）
  - WS 接收结构化指令并回写改写结果（Task 01/03）
  - WS 对无效指令做容错（Task 01 容错）
  - 改写链路走模型网关 + Mock 降级（Task 02/03）
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_backward_compatible(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_buyer_message_api_returns_result(client):
    r = client.post(
        "/api/test/buyer_message",
        json={"session_id": "S-UNIT", "message": "退款怎么还没到账？都三天了"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == "S-UNIT"
    assert "result" in body
    assert "draft_reply" in body["result"]
    assert "insight" in body["result"]


def test_ws_rewrite_valid_command(client, monkeypatch):
    # 强制走 mock 改写：断言文案确定；真模型输出文案不固定，不适合做单测断言
    from app.integrations.model.gateway import gateway

    monkeypatch.setattr(gateway, "is_available", lambda *a, **k: False)
    with client.websocket_connect("/api/chat/stream/S-UNIT") as ws:
        ws.send_json({"command": "adjust_tone", "params": {"tone": "polite"}, "draft": "退款会尽快处理"})
        msg = ws.receive_json()
        assert msg["type"] == "rewrite"
        assert msg["command"] == "adjust_tone"
        assert "退款会尽快处理" in msg["rewritten"]
        assert "polite" in msg["rewritten"]


def test_ws_invalid_command_is_tolerated(client):
    with client.websocket_connect("/api/chat/stream/S-UNIT") as ws:
        # 非 JSON 文本 -> BAD_JSON 容错（不中断连接）
        ws.send_text("not-a-json")
        err = ws.receive_json()
        assert err["type"] == "error"
        assert err["code"] == "BAD_JSON"

        # 未知指令（有 command 字段但非法）
        ws.send_json({"command": "not_supported", "draft": "x"})
        err2 = ws.receive_json()
        assert err2["type"] == "error"
        assert err2["code"] == "INVALID_COMMAND"

        # 改写指令缺 draft
        ws.send_json({"command": "adjust_tone"})
        err3 = ws.receive_json()
        assert err3["type"] == "error"
        assert err3["code"] == "EMPTY_DRAFT"


def test_ws_broadcast_from_test_api(client):
    with client.websocket_connect("/api/chat/stream/S-BROADCAST") as ws:
        r = client.post(
            "/api/test/buyer_message",
            json={"session_id": "S-BROADCAST", "message": "我的快递三天没动了"},
        )
        assert r.status_code == 200
        # 广播帧应实时到达 WS 客户端
        frame = ws.receive_json()
        assert frame["type"] == "analysis"
        assert frame["session_id"] == "S-BROADCAST"
        assert "result" in frame


def test_optimize_expression_command(client, monkeypatch):
    # 强制走 mock 改写：断言文案确定（同上）
    from app.integrations.model.gateway import gateway

    monkeypatch.setattr(gateway, "is_available", lambda *a, **k: False)
    with client.websocket_connect("/api/chat/stream/S-UNIT") as ws:
        ws.send_json({"command": "optimize_expression", "draft": "关于您的订单我们这边已经在处理了请您耐心等待"})
        msg = ws.receive_json()
        assert msg["type"] == "rewrite"
        assert msg["command"] == "optimize_expression"
        assert "表达已优化" in msg["rewritten"]
