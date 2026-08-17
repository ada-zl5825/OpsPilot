from pathlib import Path
from uuid import uuid4

from tests.unit.investigation_fakes import successful_ask

from opspilot.domain.incidents import IncidentRun, IncidentStatus
from opspilot.investigation.budget import ToolBudget
from opspilot.investigation.evidence import collect_evidence
from opspilot.investigation.replay import replay_events, replay_store
from opspilot.investigation.store import InMemoryInvestigationStore, JsonlInvestigationStore


def _run() -> IncidentRun:
    from datetime import UTC, datetime

    from opspilot.investigation.constants import PROMPT_VERSION, TOOL_CATALOG_VERSION

    return IncidentRun(
        run_id=uuid4(),
        scenario_id="S01",
        source="benchmark",
        status=IncidentStatus.INVESTIGATING,
        model="azure/gpt-4o",
        prompt_version=PROMPT_VERSION,
        tool_catalog_version=TOOL_CATALOG_VERSION,
        started_at=datetime.now(UTC),
    )


def test_jsonl_store_round_trip_and_replay(tmp_path: Path) -> None:
    store = JsonlInvestigationStore(tmp_path)
    run = _run()
    ask = successful_ask(["query_service_metrics", "query_service_logs"])
    events = [item.model_copy(update={"run_id": run.run_id}) for item in ask.events]
    store.save_run(run)
    store.append_events(events)
    evidence = collect_evidence(run.run_id, events)
    store.replace_evidence(run.run_id, evidence)

    loaded = store.list_events(run.run_id)
    assert len(loaded) == len(events)
    replayed = replay_events(run, loaded, ToolBudget())
    assert replayed.successful
    assert replayed.diagnosis is not None
    assert replayed.diagnosis.evidence_ids
    assert {item.evidence_id for item in replayed.evidence} == set(replayed.diagnosis.evidence_ids)


def test_replay_store_refuses_to_treat_failure_as_success() -> None:
    store = InMemoryInvestigationStore()
    run = _run()
    run.status = IncidentStatus.EVIDENCE_INSUFFICIENT
    store.save_run(run)
    replayed = replay_store(store, run.run_id)
    assert replayed.successful is False
    assert replayed.status is not IncidentStatus.DIAGNOSIS_COMPLETE
    assert replayed.status is not IncidentStatus.RESOLVED


def test_replay_is_deterministic_for_evidence_ids(tmp_path: Path) -> None:
    store = JsonlInvestigationStore(tmp_path)
    run = _run()
    ask = successful_ask(["get_trace_summary"])
    store.save_run(run)
    store.append_events([item.model_copy(update={"run_id": run.run_id}) for item in ask.events])
    first = replay_store(store, run.run_id)
    second = replay_store(store, run.run_id)
    assert [item.evidence_id for item in first.evidence] == [
        item.evidence_id for item in second.evidence
    ]
    assert first.status == second.status
