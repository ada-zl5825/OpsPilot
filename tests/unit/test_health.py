from fastapi.testclient import TestClient

from opspilot.api.app import create_app


def test_health() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["phase"] == "3"


def test_execute_route_exists_but_not_implemented() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/proposals/00000000-0000-0000-0000-000000000001/execute",
        headers={"Idempotency-Key": "test"},
    )
    assert response.status_code == 501
