from fastapi.testclient import TestClient

from opspilot.api.app import create_app


def test_health() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["phase"] == "5"


def test_execute_unknown_proposal_is_not_a_write() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/proposals/00000000-0000-0000-0000-000000000001/execute",
        json={
            "actor_id": "sre-1",
            "actor_role": "sre",
            "proposal_digest": "0" * 64,
        },
        headers={"Idempotency-Key": "test"},
    )
    assert response.status_code == 404
