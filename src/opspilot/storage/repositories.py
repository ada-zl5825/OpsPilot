from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from opspilot.domain.evidence import Evidence, Hypothesis
from opspilot.domain.incidents import IncidentRun
from opspilot.investigation.store import InvestigationStore
from opspilot.telemetry.events import AgentEvent


class InvestigationRepository:
    """Persist investigation records through the Phase 3 event store."""

    def __init__(self, store: InvestigationStore) -> None:
        self._store = store

    def save_run(self, run: IncidentRun) -> None:
        self._store.save_run(run)

    def get_run(self, run_id: UUID) -> IncidentRun | None:
        return self._store.get_run(run_id)

    def list_events(self, run_id: UUID) -> list[AgentEvent]:
        return self._store.list_events(run_id)

    def append_events(self, events: Sequence[AgentEvent]) -> None:
        self._store.append_events(events)

    def list_evidence(self, run_id: UUID) -> list[Evidence]:
        return self._store.list_evidence(run_id)

    def list_hypotheses(self, run_id: UUID) -> list[Hypothesis]:
        return self._store.list_hypotheses(run_id)
