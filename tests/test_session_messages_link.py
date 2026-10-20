from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Message, ServiceEvent


def test_list_messages_s159(seeded_client: TestClient):
    """验证能正常拉取 S00159 的历史消息，结构符合接口规范。"""
    resp = seeded_client.get("/api/sessions/S00159/messages")
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    data = body["data"]
    items = data["items"]
    assert len(items) >= 4

    # 验证排序递增
    seqs = [item["seq_no"] for item in items]
    assert seqs == sorted(seqs)

    # 验证字段完整性
    for item in items:
        assert "message_id" in item
        assert "role" in item
        assert "message_text" in item
        assert "sent_at" in item


def test_create_message_agent(seeded_client: TestClient, seeded_db_session: Session):
    """验证客服角色发送消息，支持持久化并记录 ServiceEvent。"""
    payload = {
        "role": "agent",
        "content": "您好，我们已为您加急处理补发事宜。",
        "send": True,
        "sender_label": "客服小美",
    }
    resp = seeded_client.post("/api/sessions/S00159/messages", json=payload)
    assert resp.status_code == 200
    res_data = resp.json()["data"]
    assert res_data["send"] is True
    assert res_data["message_id"].startswith("m-")
    assert res_data["event_id"].startswith("e-")

    # 验证数据库中消息落库
    msg = seeded_db_session.get(Message, res_data["message_id"])
    assert msg is not None
    assert msg.role == "agent"
    assert msg.sender_label == "客服小美"
    assert msg.message_text == payload["content"]

    # 验证对应审计与时间线事件落库
    event = seeded_db_session.get(ServiceEvent, res_data["event_id"])
    assert event is not None
    assert event.event_type == "message_sent"
    assert event.actor_type == "operator"
    assert event.title == "客服发送消息"


def test_create_message_buyer(seeded_client: TestClient, seeded_db_session: Session):
    """验证买家角色（role='buyer'）兼容性与默认 label 自动填充。"""
    payload = {
        "role": "buyer",
        "content": "请问大概什么时候能送到？",
        "send": True,
    }
    resp = seeded_client.post("/api/sessions/S00159/messages", json=payload)
    assert resp.status_code == 200
    res_data = resp.json()["data"]

    msg = seeded_db_session.get(Message, res_data["message_id"])
    assert msg is not None
    assert msg.role == "buyer"
    assert msg.sender_label == "消费者"  # 自动缺省为“消费者”

    event = seeded_db_session.get(ServiceEvent, res_data["event_id"])
    assert event is not None
    assert event.event_type == "message_received"
    assert event.actor_type == "consumer"
    assert event.title == "消费者发送消息"


def test_create_message_system(seeded_client: TestClient, seeded_db_session: Session):
    """验证系统消息角色与默认 label。"""
    payload = {
        "role": "system",
        "content": "[系统提示] 物流运单已生成：SF1000000000",
        "send": True,
    }
    resp = seeded_client.post("/api/sessions/S00159/messages", json=payload)
    assert resp.status_code == 200
    res_data = resp.json()["data"]

    msg = seeded_db_session.get(Message, res_data["message_id"])
    assert msg is not None
    assert msg.sender_label == "系统"


def test_create_message_not_found(seeded_client: TestClient):
    """对不存在的 session_id 发送消息，应返回 404。"""
    resp = seeded_client.post(
        "/api/sessions/NON_EXISTENT_SESSION/messages",
        json={"role": "agent", "content": "hello"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_create_message_invalid_payload(seeded_client: TestClient):
    """发送空 content 应触发 400 校验异常。"""
    resp = seeded_client.post(
        "/api/sessions/S00159/messages",
        json={"role": "agent", "content": ""},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_PARAMETER"


def test_message_history_persistence_roundtrip(seeded_client: TestClient):
    """端到端往返闭环验证：拉取 -> 发送客服 -> 发送买家 -> 再次拉取。"""
    # 1. 初始拉取
    r1 = seeded_client.get("/api/sessions/S00159/messages")
    initial_count = len(r1.json()["data"]["items"])

    # 2. 客服发言
    seeded_client.post(
        "/api/sessions/S00159/messages",
        json={"role": "agent", "content": "客服正在为您核实"},
    )

    # 3. 买家发言
    seeded_client.post(
        "/api/sessions/S00159/messages",
        json={"role": "buyer", "content": "买家等待核实结果"},
    )

    # 4. 再次拉取，验证数量增加且尾部包含刚才的两条
    r2 = seeded_client.get("/api/sessions/S00159/messages")
    new_items = r2.json()["data"]["items"]
    assert len(new_items) == initial_count + 2
    assert new_items[-2]["role"] == "agent"
    assert new_items[-2]["message_text"] == "客服正在为您核实"
    assert new_items[-1]["role"] == "buyer"
    assert new_items[-1]["message_text"] == "买家等待核实结果"
