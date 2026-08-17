from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from opspilot.api.app import create_app
from opspilot.api.dependencies import remediation_plane
from opspilot.domain.remediation import RemediationActionType
from opspilot.remediation.clock import FrozenClock
from opspilot.remediation.service import ControlPlane


def _client(plane: ControlPlane | None = None) -> tuple[TestClient, ControlPlane]:
    plane = plane or ControlPlane(clock=FrozenClock(datetime(2026, 8, 17, 12, 0, tzinfo=UTC)))
    app = create_app()
    app.dependency_overrides[remediation_plane] = lambda: plane
    return TestClient(app), plane


def _create(client: TestClient, **overrides: object) -> dict:
    payload = {
        "action_type": RemediationActionType.RESTART_WORKLOAD.value,
        "service": "checkout",
        "rationale": "restart after checkout 5xx evidence",
        "expected_effect": "checkout recovers",
    }
    payload.update(overrides)
    response = client.post(f"/api/incidents/{uuid4()}/proposals", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_api_approve_execute_and_list() -> None:
    client, plane = _client()
    created = _create(client)
    proposal_id = created["proposal_id"]
    digest = created["digest"]
    listed = client.get(f"/api/incidents/{created['incident_run_id']}/proposals")
    assert listed.status_code == 200
    assert listed.json()["proposals"][0]["proposal_id"] == proposal_id

    denied = client.post(
        f"/api/proposals/{proposal_id}/execute",
        json={"actor_id": "sre-1", "actor_role": "sre", "proposal_digest": digest},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "unapproved_write"
    assert plane.write_count() == 0

    approved = client.post(
        f"/api/proposals/{proposal_id}/approve",
        json={"actor_id": "sre-1", "actor_role": "sre", "proposal_digest": digest},
    )
    assert approved.status_code == 200
    executed = client.post(
        f"/api/proposals/{proposal_id}/execute",
        json={"actor_id": "sre-1", "actor_role": "sre", "proposal_digest": digest},
    )
    assert executed.status_code == 200
    assert executed.json()["status"] == "succeeded"
    assert plane.write_count() == 1


def test_execute_unknown_proposal_is_404() -> None:
    client, plane = _client()
    response = client.post(
        "/api/proposals/00000000-0000-0000-0000-000000000001/execute",
        json={
            "actor_id": "sre-1",
            "actor_role": "sre",
            "proposal_digest": "0" * 64,
        },
    )
    assert response.status_code == 404
    assert plane.write_count() == 0


def test_digest_mismatch_on_approve_is_403() -> None:
    client, plane = _client()
    created = _create(client)
    response = client.post(
        f"/api/proposals/{created['proposal_id']}/approve",
        json={"actor_id": "sre-1", "actor_role": "sre", "proposal_digest": "a" * 64},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "digest_mismatch"
    assert plane.write_count() == 0
