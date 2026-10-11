# 健康检查与统一响应封装的基础契约测试

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200

    body = response.json()
    assert body["error"] is None

    data = body["data"]
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["model_provider"] in {"bailian", "mock"}
    assert data["version"]
    assert data["server_time"].endswith("+08:00")

    assert body["meta"]["request_id"]
    assert response.headers["x-request-id"]


def test_health_echoes_request_id(client: TestClient) -> None:
    response = client.get("/api/health", headers={"X-Request-ID": "req_test_001"})
    assert response.status_code == 200
    assert response.json()["meta"]["request_id"] == "req_test_001"
    assert response.headers["x-request-id"] == "req_test_001"


def test_unknown_route_uses_envelope(client: TestClient) -> None:
    response = client.get("/api/not-exist")
    assert response.status_code == 404

    body = response.json()
    assert body["data"] is None
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["meta"]["request_id"]


def test_session_not_found_shape(client: TestClient) -> None:
    response = client.get("/api/sessions/S99999")
    assert response.status_code == 404

    body = response.json()
    assert body["data"] is None
    assert body["error"]["code"] == "SESSION_NOT_FOUND"
    assert body["error"]["details"]["session_id"] == "S99999"
