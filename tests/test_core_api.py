# 核心业务 API 契约测试：客户/会话/消息/订单/工单（含 PATCH 更新）
#
# 临时库灌入 baseline-v1 等价数据（见 tests/conftest.py seeded_client）：
#   C00005（会话 S00004+S00005、订单 O00004、工单 T00004）、C00015（S00015/O00015）、C00159（S00159/O00159/T00159）。

from fastapi.testclient import TestClient


# ------------------------------------------------------------ 客户
def test_customer_detail(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/customers/C00005")
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["customer_id"] == "C00005"
    assert data["display_name_masked"] == "魏h**"
    assert data["risk_level"] == "L2"
    assert data["statistics"] == {
        "session_count": 2,
        "order_count": 1,
        "ticket_count": 1,
        "open_ticket_count": 1,
    }
    assert data["created_at"].endswith("+08:00")


def test_customer_not_found(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/customers/C99999")
    assert response.status_code == 404

    error = response.json()["error"]
    assert error["code"] == "CUSTOMER_NOT_FOUND"
    assert error["details"]["customer_id"] == "C99999"


def test_customer_timeline(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/customers/C00005/timeline")
    assert response.status_code == 200

    body = response.json()
    assert body["meta"]["total"] == 3
    assert all(item["event_id"] for item in body["data"]["items"])


# ------------------------------------------------------------ 会话
def test_session_list_default_and_customer_filter(seeded_client: TestClient) -> None:
    body = seeded_client.get("/api/sessions").json()
    assert body["meta"]["total"] == 4

    filtered = seeded_client.get("/api/sessions", params={"customer_id": "C00005"}).json()
    assert filtered["meta"]["total"] == 2
    items = filtered["data"]["items"]
    assert {item["session_id"] for item in items} == {"S00004", "S00005"}
    # 承诺只读数据已下线：列表项不再返回承诺计数，保留未闭环工单计数
    assert all("active_promise_count" not in item for item in items)
    assert all("open_ticket_count" in item for item in items)


def test_session_detail_includes(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/sessions/S00005", params={"include": "events,orders,tickets"})
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["session"]["session_id"] == "S00005"
    assert data["session"]["open_ticket_count"] == 1
    assert len(data["messages"]) >= 1
    # 承诺与副驾数据已下线：详情不再返回 promises / copilot
    assert "promises" not in data
    assert "copilot" not in data
    assert {order["order_id"] for order in data["orders"]} == {"O00004"}
    assert {ticket["ticket_id"] for ticket in data["tickets"]} == {"T00004"}
    assert {event["title"] for event in data["events"]} == {"消费者再次进线催办退款"}


# ------------------------------------------------------------ 聊天记录检索
def test_session_messages_asc_and_desc(seeded_client: TestClient) -> None:
    body = seeded_client.get("/api/sessions/S00159/messages").json()
    assert body["meta"]["total"] == 4
    assert [item["seq_no"] for item in body["data"]["items"]] == [1, 2, 3, 4]

    desc = seeded_client.get("/api/sessions/S00159/messages", params={"order": "desc", "page_size": 2}).json()
    assert desc["meta"]["total"] == 4
    assert [item["seq_no"] for item in desc["data"]["items"]] == [4, 3]


def test_session_messages_not_found(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/sessions/S99999/messages")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


# ------------------------------------------------------------ 订单
def test_orders_by_order_no(seeded_client: TestClient) -> None:
    body = seeded_client.get("/api/orders", params={"order_no": "O00004"}).json()
    assert body["meta"]["total"] == 1

    order = body["data"]["items"][0]
    assert order["order_id"] == "O00004"
    assert order["paid_amount_display"] == "¥198.00"
    assert order["related_ticket_ids"] == ["T00004"]


def test_orders_by_customer_and_session(seeded_client: TestClient) -> None:
    assert seeded_client.get("/api/orders").json()["meta"]["total"] == 3
    assert seeded_client.get("/api/orders", params={"customer_id": "C00159"}).json()["meta"]["total"] == 1
    assert seeded_client.get("/api/orders", params={"session_id": "S00015"}).json()["meta"]["total"] == 1


def test_order_detail_not_found(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/orders/O99999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"


# ------------------------------------------------------------ 工单
def test_ticket_detail_with_events(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/tickets/T00004", params={"include": "events"})
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["status"] == "in_progress"
    assert data["detail"]["transfer_status"] == "处理中"
    assert {event["event_type"] for event in data["events"]} == {"ticket_status"}


def test_ticket_patch_status_writes_audit(seeded_client: TestClient) -> None:
    response = seeded_client.patch(
        "/api/tickets/T00159",
        json={"status": "completed", "note": "补发完成，物流单号已同步"},
        headers={"X-Operator-ID": "G001"},
    )
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["completed_at"] is not None

    detail = seeded_client.get("/api/tickets/T00159", params={"include": "events"}).json()["data"]
    audit = [event for event in detail["events"] if event["actor_type"] == "operator"]
    assert len(audit) == 1
    assert audit[0]["actor_id"] == "G001"
    assert audit[0]["content"] == "补发完成，物流单号已同步"
    assert "pending" in audit[0]["title"] and "completed" in audit[0]["title"]

    # 统计联动：C00159 未闭环工单数降为 0
    customer = seeded_client.get("/api/customers/C00159").json()["data"]
    assert customer["statistics"]["open_ticket_count"] == 0


def test_ticket_patch_priority_and_assignee(seeded_client: TestClient) -> None:
    response = seeded_client.patch("/api/tickets/T00004", json={"priority": "critical", "assignee": "G009"})
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["priority"] == "critical"
    assert data["assignee"] == "G009"

    detail = seeded_client.get("/api/tickets/T00004", params={"include": "events"}).json()["data"]
    assert len([event for event in detail["events"] if event["event_type"] == "ticket_update"]) == 1


def test_ticket_patch_no_change_is_idempotent(seeded_client: TestClient) -> None:
    response = seeded_client.patch("/api/tickets/T00004", json={"status": "in_progress"})
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "in_progress"

    detail = seeded_client.get("/api/tickets/T00004", params={"include": "events"}).json()["data"]
    assert [event for event in detail["events"] if event["actor_type"] == "operator"] == []


def test_ticket_patch_requires_at_least_one_field(seeded_client: TestClient) -> None:
    response = seeded_client.patch("/api/tickets/T00004", json={})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PARAMETER"


def test_ticket_patch_not_found(seeded_client: TestClient) -> None:
    response = seeded_client.patch("/api/tickets/T99999", json={"status": "completed"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TICKET_NOT_FOUND"


# ------------------------------------------------------------ 范围外模块已下线（未挂载）
def test_deprecated_routes_unmounted(seeded_client: TestClient) -> None:
    assert seeded_client.get("/api/sessions/S00005/copilot").status_code == 404
    assert seeded_client.get("/api/sessions/S00005/stream").status_code == 404
    assert seeded_client.get("/api/risk-queue").status_code == 404
