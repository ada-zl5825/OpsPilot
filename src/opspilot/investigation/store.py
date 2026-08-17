from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from threading import Lock
from typing import Protocol
from uuid import UUID

from opspilot.domain.evidence import Evidence, Hypothesis
from opspilot.domain.incidents import IncidentRun
from opspilot.telemetry.events import AgentEvent


class InvestigationStore(Protocol):
    def save_run(self, run: IncidentRun) -> None: ...
    def get_run(self, run_id: UUID) -> IncidentRun | None: ...
    def list_runs(self) -> list[IncidentRun]: ...
    def append_events(self, events: Sequence[AgentEvent]) -> None: ...
    def list_events(self, run_id: UUID) -> list[AgentEvent]: ...
    def replace_evidence(self, run_id: UUID, evidence: Sequence[Evidence]) -> None: ...
    def list_evidence(self, run_id: UUID) -> list[Evidence]: ...
    def replace_hypotheses(self, run_id: UUID, hypotheses: Sequence[Hypothesis]) -> None: ...
    def list_hypotheses(self, run_id: UUID) -> list[Hypothesis]: ...


class InMemoryInvestigationStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._runs: dict[UUID, IncidentRun] = {}
        self._events: dict[UUID, list[AgentEvent]] = defaultdict(list)
        self._evidence: dict[UUID, list[Evidence]] = defaultdict(list)
        self._hypotheses: dict[UUID, list[Hypothesis]] = defaultdict(list)

    def save_run(self, run: IncidentRun) -> None:
        with self._lock:
            self._runs[run.run_id] = run

    def get_run(self, run_id: UUID) -> IncidentRun | None:
        with self._lock:
            return self._runs.get(run_id)

    def list_runs(self) -> list[IncidentRun]:
        with self._lock:
            return list(self._runs.values())

    def append_events(self, events: Sequence[AgentEvent]) -> None:
        with self._lock:
            for event in events:
                self._events[event.run_id].append(event)

    def list_events(self, run_id: UUID) -> list[AgentEvent]:
        with self._lock:
            return list(self._events.get(run_id, []))

    def replace_evidence(self, run_id: UUID, evidence: Sequence[Evidence]) -> None:
        with self._lock:
            self._evidence[run_id] = list(evidence)

    def list_evidence(self, run_id: UUID) -> list[Evidence]:
        with self._lock:
            return list(self._evidence.get(run_id, []))

    def replace_hypotheses(self, run_id: UUID, hypotheses: Sequence[Hypothesis]) -> None:
        with self._lock:
            self._hypotheses[run_id] = list(hypotheses)

    def list_hypotheses(self, run_id: UUID) -> list[Hypothesis]:
        with self._lock:
            return list(self._hypotheses.get(run_id, []))


class JsonlInvestigationStore:
    """Durable stream-event store. One directory per run; events are append-only JSONL."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def _dir(self, run_id: UUID) -> Path:
        path = self._root / str(run_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_run(self, run: IncidentRun) -> None:
        with self._lock:
            path = self._dir(run.run_id) / "run.json"
            path.write_text(run.model_dump_json(indent=2), encoding="utf-8")

    def get_run(self, run_id: UUID) -> IncidentRun | None:
        path = self._root / str(run_id) / "run.json"
        if not path.exists():
            return None
        return IncidentRun.model_validate_json(path.read_text(encoding="utf-8"))

    def list_runs(self) -> list[IncidentRun]:
        runs: list[IncidentRun] = []
        for path in sorted(self._root.glob("*/run.json")):
            runs.append(IncidentRun.model_validate_json(path.read_text(encoding="utf-8")))
        return runs

    def append_events(self, events: Sequence[AgentEvent]) -> None:
        with self._lock:
            by_run: dict[UUID, list[AgentEvent]] = defaultdict(list)
            for event in events:
                by_run[event.run_id].append(event)
            for run_id, group in by_run.items():
                path = self._dir(run_id) / "events.jsonl"
                with path.open("a", encoding="utf-8") as handle:
                    for event in group:
                        handle.write(event.model_dump_json() + "\n")

    def list_events(self, run_id: UUID) -> list[AgentEvent]:
        path = self._root / str(run_id) / "events.jsonl"
        if not path.exists():
            return []
        events: list[AgentEvent] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(AgentEvent.model_validate(json.loads(line)))
        return events

    def replace_evidence(self, run_id: UUID, evidence: Sequence[Evidence]) -> None:
        with self._lock:
            path = self._dir(run_id) / "evidence.json"
            payload = [item.model_dump(mode="json") for item in evidence]
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_evidence(self, run_id: UUID) -> list[Evidence]:
        path = self._root / str(run_id) / "evidence.json"
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [Evidence.model_validate(item) for item in payload]

    def replace_hypotheses(self, run_id: UUID, hypotheses: Sequence[Hypothesis]) -> None:
        with self._lock:
            path = self._dir(run_id) / "hypotheses.json"
            payload = [item.model_dump(mode="json") for item in hypotheses]
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_hypotheses(self, run_id: UUID) -> list[Hypothesis]:
        path = self._root / str(run_id) / "hypotheses.json"
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [Hypothesis.model_validate(item) for item in payload]
