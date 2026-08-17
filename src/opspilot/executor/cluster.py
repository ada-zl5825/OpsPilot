from __future__ import annotations

from threading import Lock
from typing import Protocol

from pydantic import BaseModel, Field

from opspilot.executor.commands import TypedAction, TypedCommand
from opspilot.policy.rules import ALLOWED_NAMESPACES, ALLOWED_SERVICES

DEFAULT_REVISION = "1.4.1"
PREVIOUS_REVISION = "1.4.0"


class WorkloadSnapshot(BaseModel):
    kind: str = "Deployment"
    name: str
    namespace: str = "lab"
    replicas: int = 1
    revision: str = DEFAULT_REVISION
    previous_revision: str = PREVIOUS_REVISION
    restart_count: int = 0
    ready: bool = True
    healthy: bool = True
    latency_ms: int = 80
    status_code: int = 200
    write_generation: int = 0


class ApplyResult(BaseModel):
    snapshot: WorkloadSnapshot
    command: TypedCommand
    argv: list[str] = Field(default_factory=list)


class ClusterBackend(Protocol):
    def snapshot(self, name: str, namespace: str = "lab") -> WorkloadSnapshot: ...

    def apply(self, command: TypedCommand) -> ApplyResult: ...

    def write_count(self) -> int: ...

    def writes(self) -> list[TypedCommand]: ...

    def inject_fault(self, name: str, namespace: str = "lab") -> WorkloadSnapshot: ...


class InMemoryCluster:
    """Deterministic lab cluster. The only mutation entry is apply()."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._workloads: dict[tuple[str, str], WorkloadSnapshot] = {}
        self._writes: list[TypedCommand] = []
        for name in ALLOWED_SERVICES:
            self._workloads[("lab", name)] = WorkloadSnapshot(name=name)

    def snapshot(self, name: str, namespace: str = "lab") -> WorkloadSnapshot:
        with self._lock:
            return self._require(name, namespace).model_copy(deep=True)

    def apply(self, command: TypedCommand) -> ApplyResult:
        if command.namespace not in ALLOWED_NAMESPACES:
            raise PermissionError(f"refusing write to namespace {command.namespace}")
        if command.name not in ALLOWED_SERVICES:
            raise PermissionError(f"refusing write to service {command.name}")
        with self._lock:
            current = self._require(command.name, command.namespace)
            updated = current.model_copy(deep=True)
            if command.action is TypedAction.RESTART:
                updated.restart_count += 1
                updated.ready = True
                updated.healthy = True
                updated.latency_ms = 80
                updated.status_code = 200
            elif command.action is TypedAction.SCALE:
                assert command.replicas is not None
                updated.replicas = command.replicas
                updated.ready = command.replicas >= 1
                updated.healthy = command.replicas >= 1
                updated.status_code = 200 if command.replicas >= 1 else 503
            elif command.action is TypedAction.ROLLBACK:
                target_revision = command.to_revision or current.previous_revision
                updated.previous_revision = current.revision
                updated.revision = target_revision
                updated.ready = True
                updated.healthy = True
                updated.latency_ms = 80
                updated.status_code = 200
            updated.write_generation = current.write_generation + 1
            self._workloads[(command.namespace, command.name)] = updated
            self._writes.append(command)
            return ApplyResult(snapshot=updated, command=command, argv=command.argv())

    def write_count(self) -> int:
        with self._lock:
            return len(self._writes)

    def writes(self) -> list[TypedCommand]:
        with self._lock:
            return [item.model_copy(deep=True) for item in self._writes]

    def inject_fault(self, name: str, namespace: str = "lab") -> WorkloadSnapshot:
        with self._lock:
            current = self._require(name, namespace)
            current.healthy = False
            current.ready = False
            current.status_code = 500
            current.latency_ms = 2500
            current.revision = "1.4.2"
            return current.model_copy(deep=True)

    def _require(self, name: str, namespace: str) -> WorkloadSnapshot:
        key = (namespace, name)
        if key not in self._workloads:
            raise KeyError(f"unknown workload {namespace}/{name}")
        return self._workloads[key]
