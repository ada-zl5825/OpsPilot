from fastapi.testclient import TestClient

from opspilot.api.app import create_app
from opspilot.api.dependencies import investigation_store
from opspilot.investigation.store import InMemoryInvestigationStore


def _client(store: InMemoryInvestigationStore) -> TestClient:
    app = create_app()
    app.dependency_overrides[investigation_store] = lambda: store
    return TestClient(app)


def test_create_get_events_and_cancel_incident() -> None:
    store = InMemoryInvestigationStore()
    client = _client(store)
    created = client.post("/api/incidents", json={"scenario_id": "S01", "source": "manual"})
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "incident_created"
    assert body["scenario_id"] == "S01"
    run_id = body["run_id"]

    fetched = client.get(f"/api/incidents/{run_id}")
    assert fetched.status_code == 200
    assert fetched.json()["run_id"] == run_id

    events = client.get(f"/api/incidents/{run_id}/events")
    assert events.status_code == 200
    payload = events.json()
    assert payload["successful"] is False
    assert payload["events"] == []

    cancelled = client.post(f"/api/incidents/{run_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_missing_incident_is_404() -> None:
    client = _client(InMemoryInvestigationStore())
    response = client.get("/api/incidents/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 404
