from __future__ import annotations

from datetime import timedelta
from threading import Lock
from typing import Any
from uuid import UUID, uuid4

from opspilot.domain.approvals import ApprovalDecision
from opspilot.domain.remediation import (
    DryRunResult,
    ExecutionAttempt,
    ProposalStatus,
    RemediationActionType,
    RemediationProposal,
    ResourceRef,
    RollbackPlan,
)
from opspilot.executor.cluster import ClusterBackend, InMemoryCluster, WorkloadSnapshot
from opspilot.executor.commands import CommandCompileError, TypedCommand, compile_typed_command
from opspilot.executor.idempotency import digest_payload, proposal_digest
from opspilot.executor.lab_executor import LabExecutor
from opspilot.executor.rollback import inverse_command
from opspilot.policy.engine import PolicyEngine
from opspilot.policy.redaction import redact_mapping
from opspilot.policy.rules import ALLOWED_NAMESPACES
from opspilot.remediation.clock import Clock, SystemClock
from opspilot.remediation.errors import RemediationError
from opspilot.remediation.models import AuditEvent, ProposalRecord
from opspilot.remediation.store import InMemoryRemediationStore, RemediationStore
from opspilot.telemetry.tracing import investigation_span
from opspilot.verification.recovery import RecoveryReport, verify_snapshot

FORBIDDEN_ACTOR_IDS = frozenset({"agent", "holmes", "holmesgpt", "system", "opspilot-agent", "llm"})
FORBIDDEN_ROLES = frozenset({"agent", "system", "llm"})
DEFAULT_TTL_SECONDS = 1800


class ControlPlane:
    """Deterministic write path. cluster.apply is only reached from execute/rollback."""

    def __init__(
        self,
        *,
        store: RemediationStore | None = None,
        cluster: ClusterBackend | None = None,
        policy: PolicyEngine | None = None,
        clock: Clock | None = None,
        default_ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.store = store or InMemoryRemediationStore()
        self.cluster = cluster or InMemoryCluster()
        self.policy = policy or PolicyEngine()
        self.clock = clock or SystemClock()
        self.default_ttl_seconds = default_ttl_seconds
        self._executor = LabExecutor(self.cluster)
        self._lock = Lock()
        self._key_locks: dict[str, Lock] = {}

    def propose(
        self,
        *,
        incident_run_id: UUID,
        action_type: RemediationActionType,
        service: str,
        namespace: str = "lab",
        parameters: dict[str, Any] | None = None,
        rationale: str,
        expected_effect: str,
        evidence_ids: list[UUID] | None = None,
        idempotency_key: str = "",
        expires_in_seconds: int | None = None,
    ) -> ProposalRecord:
        params = dict(parameters or {})
        key = idempotency_key or _default_idempotency_key(
            incident_run_id, action_type, service, namespace, params
        )
        existing = self.store.get_by_idempotency_key(key)
        if existing is not None:
            return existing

        target = ResourceRef(kind="Deployment", name=service, namespace=namespace, service=service)
        snapshot = _safe_snapshot(self.cluster, service, namespace)
        rollback = _default_rollback_plan(action_type, target, snapshot)
        now = self.clock.now()
        proposal = RemediationProposal(
            proposal_id=uuid4(),
            incident_run_id=incident_run_id,
            action_type=action_type,
            target=target,
            parameters=params,
            rationale=rationale,
            evidence_ids=list(evidence_ids or []),
            expected_effect=expected_effect,
            risk_level="medium",
            rollback_plan=rollback,
            idempotency_key=key,
            expires_at=now + timedelta(seconds=expires_in_seconds or self.default_ttl_seconds),
        )
        with investigation_span(
            "remediation.policy",
            action_type=action_type.value,
            service=service,
            namespace=namespace,
        ):
            decision = self.policy.evaluate(proposal)
        proposal.risk_level = decision.risk
        digest = proposal_digest(proposal)
        status = (
            ProposalStatus.AWAITING_APPROVAL if decision.allowed else ProposalStatus.POLICY_REJECTED
        )
        record = ProposalRecord(
            proposal=proposal,
            digest=digest,
            status=status,
            created_at=now,
        )
        self._audit(
            record,
            action="propose",
            actor_id="agent",
            actor_role="agent",
            result="recorded" if decision.allowed else "denied",
            error_code=None if decision.allowed else "policy_denied",
            detail="; ".join(decision.reasons),
        )
        self.store.save(record)
        return record

    def dry_run(self, proposal_id: UUID) -> DryRunResult:
        record = self._require(proposal_id)
        self._reject_if_expired(record)
        with investigation_span("remediation.policy", proposal_id=str(proposal_id)):
            decision = self.policy.evaluate(record.proposal)
        violations = list(decision.reasons)
        command: TypedCommand | None = None
        try:
            command = compile_typed_command(record.proposal)
        except CommandCompileError as exc:
            violations.extend(reason for reason in exc.reasons if reason not in violations)
        snapshot = _safe_snapshot(
            self.cluster, record.proposal.target.name, record.proposal.target.namespace
        )
        allowed = decision.allowed and command is not None
        summary = _dry_run_summary(record.proposal, command, snapshot, allowed, violations)
        result = DryRunResult(allowed=allowed, summary=summary, violations=violations)
        record.proposal.dry_run_result = result
        if record.status is ProposalStatus.PROPOSED and allowed:
            record.status = ProposalStatus.AWAITING_APPROVAL
        self._audit(
            record,
            action="dry_run",
            actor_id="agent",
            actor_role="agent",
            result="accepted" if allowed else "denied",
            error_code=None if allowed else "policy_denied",
            detail=summary,
        )
        self.store.save(record)
        return result

    def approve(
        self,
        proposal_id: UUID,
        *,
        actor_id: str,
        actor_role: str,
        proposal_digest_value: str,
        reason: str | None = None,
    ) -> ApprovalDecision:
        self._assert_human(actor_id, actor_role)
        with self._lock_for(str(proposal_id)):
            record = self._require(proposal_id)
            self._reject_if_expired(record)
            self._assert_digest(record, proposal_digest_value)
            if record.status is ProposalStatus.REJECTED:
                raise RemediationError("already_rejected", "rejected proposals cannot be approved")
            if record.status is ProposalStatus.POLICY_REJECTED:
                raise RemediationError(
                    "policy_denied", "policy-rejected proposals cannot be approved"
                )
            if record.approval is not None and record.approval.decision == "approved":
                if record.approval.proposal_digest == record.digest:
                    return record.approval
                raise RemediationError(
                    "digest_mismatch", "existing approval digest no longer matches"
                )
            with investigation_span("remediation.approval", proposal_id=str(proposal_id)):
                decision = self.policy.evaluate(record.proposal)
                if not decision.allowed:
                    record.status = ProposalStatus.POLICY_REJECTED
                    self.store.save(record)
                    raise RemediationError("policy_denied", "; ".join(decision.reasons))
                dry_run = self.dry_run(proposal_id)
                if not dry_run.allowed:
                    raise RemediationError("policy_denied", "; ".join(dry_run.violations))
                record = self._require(proposal_id)
                approval = ApprovalDecision(
                    proposal_id=proposal_id,
                    decision="approved",
                    actor_id=actor_id,
                    actor_role=actor_role,
                    reason=reason,
                    proposal_digest=record.digest,
                    decided_at=self.clock.now(),
                )
                record.approval = approval
                record.status = ProposalStatus.APPROVED
                self._audit(
                    record,
                    action="approve",
                    actor_id=actor_id,
                    actor_role=actor_role,
                    result="accepted",
                    detail=reason or "",
                )
                self.store.save(record)
                return approval

    def reject(
        self,
        proposal_id: UUID,
        *,
        actor_id: str,
        actor_role: str,
        proposal_digest_value: str,
        reason: str | None = None,
    ) -> ApprovalDecision:
        self._assert_human(actor_id, actor_role)
        with self._lock_for(str(proposal_id)):
            record = self._require(proposal_id)
            self._assert_digest(record, proposal_digest_value)
            if record.approval is not None and record.approval.decision == "rejected":
                return record.approval
            if record.status is ProposalStatus.APPROVED:
                raise RemediationError("conflict", "approved proposals cannot be rejected")
            if record.succeeded():
                raise RemediationError("conflict", "executed proposals cannot be rejected")
            approval = ApprovalDecision(
                proposal_id=proposal_id,
                decision="rejected",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=reason,
                proposal_digest=record.digest,
                decided_at=self.clock.now(),
            )
            record.approval = approval
            record.status = ProposalStatus.REJECTED
            self._audit(
                record,
                action="reject",
                actor_id=actor_id,
                actor_role=actor_role,
                result="accepted",
                detail=reason or "",
            )
            self.store.save(record)
            return approval

    def execute(
        self,
        proposal_id: UUID,
        *,
        actor_id: str,
        actor_role: str,
        proposal_digest_value: str,
    ) -> ExecutionAttempt:
        self._assert_human(actor_id, actor_role)
        with self._lock_for(str(proposal_id)):
            record = self._require(proposal_id)
            self._guard_execute(record, proposal_digest_value)
            if record.succeeded():
                succeeded = next(item for item in record.executions if item.status == "succeeded")
                self._audit(
                    record,
                    action="execute",
                    actor_id=actor_id,
                    actor_role=actor_role,
                    result="recorded",
                    detail="idempotent replay",
                )
                self.store.save(record)
                return succeeded
            with investigation_span(
                "remediation.execute",
                proposal_id=str(proposal_id),
                action_type=record.proposal.action_type.value,
            ):
                snapshot = self.cluster.snapshot(
                    record.proposal.target.name, record.proposal.target.namespace
                )
                record.pre_execution_snapshot = snapshot
                command = compile_typed_command(record.proposal)
                record.last_command = command.model_dump(mode="json")
                attempt = self._executor.execute(record.proposal)
                record.executions.append(attempt)
                record.status = (
                    ProposalStatus.EXECUTED
                    if attempt.status == "succeeded"
                    else ProposalStatus.FAILED
                )
                self._audit(
                    record,
                    action="execute",
                    actor_id=actor_id,
                    actor_role=actor_role,
                    result="accepted" if attempt.status == "succeeded" else "denied",
                    error_code=attempt.error_code,
                    detail=" ".join(attempt.command_plan),
                )
                self.store.save(record)
                return attempt

    def rollback_execution(
        self,
        proposal_id: UUID,
        *,
        actor_id: str,
        actor_role: str,
        proposal_digest_value: str,
    ) -> ExecutionAttempt:
        self._assert_human(actor_id, actor_role)
        with self._lock_for(str(proposal_id)):
            record = self._require(proposal_id)
            self._assert_digest(record, proposal_digest_value)
            if not record.succeeded():
                raise RemediationError(
                    "not_executed", "cannot rollback a proposal that never executed"
                )
            if record.status is ProposalStatus.ROLLED_BACK:
                rolled = next(item for item in record.executions if item.status == "rolled_back")
                return rolled
            if record.pre_execution_snapshot is None or record.last_command is None:
                raise RemediationError("not_executed", "missing pre-execution snapshot")
            command = TypedCommand.model_validate(record.last_command)
            inverse = inverse_command(command, record.pre_execution_snapshot)
            started = self.clock.now()
            applied = self.cluster.apply(inverse)
            attempt = ExecutionAttempt(
                execution_id=uuid4(),
                proposal_id=proposal_id,
                status="rolled_back",
                command_plan=applied.argv or inverse.argv(),
                started_at=started,
                ended_at=self.clock.now(),
            )
            record.executions.append(attempt)
            record.status = ProposalStatus.ROLLED_BACK
            self._audit(
                record,
                action="rollback",
                actor_id=actor_id,
                actor_role=actor_role,
                result="accepted",
                detail=" ".join(attempt.command_plan),
            )
            self.store.save(record)
            return attempt

    def verify(
        self,
        proposal_id: UUID | None = None,
        *,
        service: str | None = None,
        namespace: str = "lab",
        max_latency_ms: int = 1500,
    ) -> RecoveryReport:
        snapshot_service = service
        if proposal_id is not None:
            record = self._require(proposal_id)
            snapshot_service = snapshot_service or record.proposal.target.name
            namespace = record.proposal.target.namespace
        if not snapshot_service:
            raise RemediationError("invalid_command", "service is required")
        with investigation_span("recovery.verify", service=snapshot_service, namespace=namespace):
            snapshot = self.cluster.snapshot(snapshot_service, namespace)
            report = verify_snapshot(snapshot, max_latency_ms=max_latency_ms)
        if proposal_id is not None:
            record = self._require(proposal_id)
            record.recovery = report
            self._audit(
                record,
                action="verify",
                actor_id="agent",
                actor_role="agent",
                result="accepted" if report.passed else "denied",
                detail="recovery passed" if report.passed else "recovery failed",
            )
            self.store.save(record)
        return report

    def get(self, proposal_id: UUID) -> ProposalRecord:
        return self._require(proposal_id)

    def list_for_run(self, run_id: UUID) -> list[ProposalRecord]:
        return self.store.list_for_run(run_id)

    def write_count(self) -> int:
        return self.cluster.write_count()

    def _guard_execute(self, record: ProposalRecord, digest_value: str) -> None:
        self._reject_if_expired(record)
        self._assert_digest(record, digest_value)
        if record.proposal.target.namespace not in ALLOWED_NAMESPACES:
            raise RemediationError("cross_namespace", "namespace is not allowlisted")
        if record.status is ProposalStatus.POLICY_REJECTED:
            raise RemediationError("policy_denied", "policy-rejected proposals cannot execute")
        if record.status is ProposalStatus.REJECTED:
            raise RemediationError("already_rejected", "rejected proposals cannot execute")
        if record.approval is None or record.approval.decision != "approved":
            raise RemediationError("unapproved_write", "proposal is not approved")
        if record.approval.proposal_digest != record.digest:
            raise RemediationError("tampered_proposal", "approval digest does not match proposal")
        if record.approval.proposal_digest != digest_value:
            raise RemediationError("digest_mismatch", "execute digest does not match approval")
        decision = self.policy.evaluate(record.proposal)
        if not decision.allowed:
            raise RemediationError("policy_denied", "; ".join(decision.reasons))
        try:
            compile_typed_command(record.proposal)
        except CommandCompileError as exc:
            raise RemediationError("invalid_command", "; ".join(exc.reasons)) from exc

    def _assert_digest(self, record: ProposalRecord, digest_value: str) -> None:
        current = proposal_digest(record.proposal)
        if current != record.digest:
            raise RemediationError("tampered_proposal", "stored proposal no longer matches digest")
        if digest_value != record.digest:
            raise RemediationError("digest_mismatch", "supplied digest does not match proposal")

    def _reject_if_expired(self, record: ProposalRecord) -> None:
        if self.clock.now() >= record.proposal.expires_at:
            record.status = ProposalStatus.EXPIRED
            self.store.save(record)
            raise RemediationError("proposal_expired", "proposal has expired")

    def _assert_human(self, actor_id: str, actor_role: str) -> None:
        if actor_id.strip().lower() in FORBIDDEN_ACTOR_IDS:
            raise RemediationError("forbidden_actor", "approver cannot be the system agent")
        if actor_role.strip().lower() in FORBIDDEN_ROLES:
            raise RemediationError("forbidden_actor", "approver role cannot be the system agent")

    def _require(self, proposal_id: UUID) -> ProposalRecord:
        record = self.store.get(proposal_id)
        if record is None:
            raise RemediationError("not_found", "proposal not found")
        return record

    def _lock_for(self, key: str) -> Lock:
        with self._lock:
            return self._key_locks.setdefault(key, Lock())

    def _audit(
        self,
        record: ProposalRecord,
        *,
        action: str,
        actor_id: str,
        actor_role: str,
        result: str,
        error_code: str | None = None,
        detail: str = "",
    ) -> None:
        target = redact_mapping(
            {
                "namespace": record.proposal.target.namespace,
                "name": record.proposal.target.name,
                "action_type": record.proposal.action_type.value,
            }
        )
        if not isinstance(target, dict):
            target = {}
        record.audit.append(
            AuditEvent(
                timestamp=self.clock.now(),
                action=action,
                actor_id=actor_id,
                actor_role=actor_role,
                proposal_id=record.proposal.proposal_id,
                digest=record.digest,
                result=result,
                error_code=error_code,
                detail=detail[:240],
                target=target,
            )
        )


def _default_idempotency_key(
    run_id: UUID,
    action_type: RemediationActionType,
    service: str,
    namespace: str,
    parameters: dict[str, Any],
) -> str:
    return digest_payload(
        {
            "incident_run_id": str(run_id),
            "action_type": action_type.value,
            "service": service,
            "namespace": namespace,
            "parameters": parameters,
        }
    )


def _default_rollback_plan(
    action_type: RemediationActionType,
    target: ResourceRef,
    snapshot: WorkloadSnapshot | None,
) -> RollbackPlan:
    parameters: dict[str, Any] = {}
    if snapshot is not None:
        if action_type is RemediationActionType.SCALE_WORKLOAD:
            parameters["replicas"] = snapshot.replicas
        if action_type is RemediationActionType.ROLLBACK_DEPLOYMENT:
            parameters["to_revision"] = snapshot.revision
    return RollbackPlan(action_type=action_type, target=target, parameters=parameters)


def _safe_snapshot(cluster: ClusterBackend, name: str, namespace: str) -> WorkloadSnapshot | None:
    try:
        return cluster.snapshot(name, namespace)
    except (KeyError, PermissionError):
        return None


def _dry_run_summary(
    proposal: RemediationProposal,
    command: TypedCommand | None,
    snapshot: WorkloadSnapshot | None,
    allowed: bool,
    violations: list[str],
) -> str:
    if not allowed:
        return "dry run blocked: " + "; ".join(violations)
    assert command is not None
    current = f"{snapshot.revision}/{snapshot.replicas}" if snapshot else "unknown"
    return (
        f"would {command.action.value} deployment/{command.name} in {command.namespace} "
        f"(current={current}; argv={' '.join(command.argv())})"
    )
