from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from opspilot.api.app import create_app


def test_offline_benchmark_api_and_baselines(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("benchmarks.harness.DEFAULT_OUT", tmp_path)
    client = TestClient(create_app())
    created = client.post(
        "/api/benchmarks/runs",
        json={"mode": "offline", "split": "eval", "gate": False},
        headers={"Idempotency-Key": "bench-1"},
    )
    assert created.status_code == 201
    body = created.json()
    run_id = body["benchmark_run_id"]
    assert body["status"] == "completed"
    assert body["report"]["summaries"]

    replayed = client.post(
        "/api/benchmarks/runs",
        json={"mode": "offline", "split": "eval"},
        headers={"Idempotency-Key": "bench-1"},
    )
    assert replayed.json()["benchmark_run_id"] == run_id

    fetched = client.get(f"/api/benchmarks/runs/{run_id}")
    assert fetched.status_code == 200
    report = client.get(f"/api/benchmarks/runs/{run_id}/report")
    assert report.status_code == 200
    assert report.json()["benchmark_version"] == "v1"

    baselines = client.get("/api/benchmarks/baselines")
    assert baselines.status_code == 200
    assert baselines.json()["baselines"][0]["benchmark_version"] == "v1"


def test_live_mode_rejected() -> None:
    client = TestClient(create_app())
    response = client.post("/api/benchmarks/runs", json={"mode": "live"})
    assert response.status_code == 400
