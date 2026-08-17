from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Protocol
from uuid import UUID

from opspilot.remediation.models import ProposalRecord


class RemediationStore(Protocol):
    def save(self, record: ProposalRecord) -> None: ...

    def get(self, proposal_id: UUID) -> ProposalRecord | None: ...

    def get_by_idempotency_key(self, key: str) -> ProposalRecord | None: ...

    def list_for_run(self, run_id: UUID) -> list[ProposalRecord]: ...


class InMemoryRemediationStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._records: dict[UUID, ProposalRecord] = {}
        self._keys: dict[str, UUID] = {}

    def save(self, record: ProposalRecord) -> None:
        with self._lock:
            self._records[record.proposal.proposal_id] = record
            self._keys[record.proposal.idempotency_key] = record.proposal.proposal_id

    def get(self, proposal_id: UUID) -> ProposalRecord | None:
        with self._lock:
            found = self._records.get(proposal_id)
            return found.model_copy(deep=True) if found else None

    def get_by_idempotency_key(self, key: str) -> ProposalRecord | None:
        with self._lock:
            proposal_id = self._keys.get(key)
            if proposal_id is None:
                return None
            found = self._records[proposal_id]
            return found.model_copy(deep=True)

    def list_for_run(self, run_id: UUID) -> list[ProposalRecord]:
        with self._lock:
            return [
                item.model_copy(deep=True)
                for item in self._records.values()
                if item.proposal.incident_run_id == run_id
            ]


class JsonRemediationStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def save(self, record: ProposalRecord) -> None:
        with self._lock:
            path = self._path(record.proposal.proposal_id)
            path.write_text(record.model_dump_json(), encoding="utf-8")

    def get(self, proposal_id: UUID) -> ProposalRecord | None:
        with self._lock:
            path = self._path(proposal_id)
            if not path.exists():
                return None
            return ProposalRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def get_by_idempotency_key(self, key: str) -> ProposalRecord | None:
        with self._lock:
            for path in self._root.glob("*.json"):
                record = ProposalRecord.model_validate_json(path.read_text(encoding="utf-8"))
                if record.proposal.idempotency_key == key:
                    return record
            return None

    def list_for_run(self, run_id: UUID) -> list[ProposalRecord]:
        with self._lock:
            records: list[ProposalRecord] = []
            for path in self._root.glob("*.json"):
                record = ProposalRecord.model_validate_json(path.read_text(encoding="utf-8"))
                if record.proposal.incident_run_id == run_id:
                    records.append(record)
            return records

    def _path(self, proposal_id: UUID) -> Path:
        return self._root / f"{proposal_id}.json"
