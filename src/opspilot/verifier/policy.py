from __future__ import annotations

from pydantic import ValidationError

from opspilot.investigation.constants import MUTATE_TOOLS, PHASE2_READ_TOOLS
from opspilot.verifier.budget import can_followup
from opspilot.verifier.schema import FollowupRequest, InvestigatorBundle, VerifierVerdict

UNSAFE_ACTION_MARKERS = (
    "execute_approved_proposal",
    "rollback_execution",
    "lab_mutate_probe",
    "shell=" + "True",
    "--token",
    "--kubeconfig",
    "--as",
)


class VerdictPolicyResult:
    def __init__(self, verdict: VerifierVerdict, notes: list[str]) -> None:
        self.verdict = verdict
        self.notes = notes


def _has_unsafe_text(values: list[str]) -> bool:
    lowered = " ".join(values).lower()
    return any(marker.lower() in lowered for marker in UNSAFE_ACTION_MARKERS)


def sanitize_followup(request: FollowupRequest) -> tuple[FollowupRequest, list[str]]:
    notes: list[str] = []
    allowed: list[str] = []
    for tool in request.suggested_tools:
        if tool in MUTATE_TOOLS:
            notes.append(f"stripped write tool from follow-up: {tool}")
            continue
        if tool not in PHASE2_READ_TOOLS:
            notes.append(f"stripped unknown tool from follow-up: {tool}")
            continue
        if tool not in allowed:
            allowed.append(tool)
    params = [item for item in request.suggested_params if isinstance(item, dict)]
    return (
        request.model_copy(update={"suggested_tools": allowed, "suggested_params": params}),
        notes,
    )


def enforce_verdict(verdict: VerifierVerdict, bundle: InvestigatorBundle) -> VerdictPolicyResult:
    notes = list(verdict.notes)
    followup = verdict.followup
    if followup is not None:
        followup, stripped = sanitize_followup(followup)
        notes.extend(stripped)

    actions = list(bundle.recommended_actions)
    if verdict.decision == "accept" and _has_unsafe_text(actions):
        notes.append("recommended actions include a write or identity override")
        return VerdictPolicyResult(
            _reject(verdict, notes, reason="unsafe recommended action"),
            notes,
        )
    if not verdict.safety_ok and verdict.decision == "accept":
        return VerdictPolicyResult(_reject(verdict, notes, reason="safety_ok is false"), notes)

    if verdict.decision == "request_followup":
        if followup is None:
            notes.append("follow-up requested without a followup object")
            return VerdictPolicyResult(_reject(verdict, notes, reason="invalid follow-up"), notes)
        if not can_followup(bundle.budget) or bundle.followup_used:
            notes.append("shared budget or follow-up cap blocked another investigation")
            if verdict.evidence_supports_conclusion and bundle.evidence and verdict.safety_ok:
                return VerdictPolicyResult(
                    verdict.model_copy(
                        update={
                            "decision": "accept",
                            "followup": None,
                            "notes": notes,
                        }
                    ),
                    notes,
                )
            return VerdictPolicyResult(
                _reject(verdict, notes, reason="follow-up blocked by shared budget"),
                notes,
            )
        return VerdictPolicyResult(
            verdict.model_copy(update={"followup": followup, "notes": notes}),
            notes,
        )

    if verdict.decision == "accept":
        if not bundle.evidence:
            notes.append("accept without successful evidence")
            return VerdictPolicyResult(_reject(verdict, notes, reason="no evidence"), notes)
        if not verdict.evidence_supports_conclusion:
            return VerdictPolicyResult(
                _reject(verdict, notes, reason="conclusion unsupported"),
                notes,
            )
        return VerdictPolicyResult(verdict.model_copy(update={"notes": notes}), notes)

    return VerdictPolicyResult(verdict.model_copy(update={"notes": notes}), notes)


def _reject(verdict: VerifierVerdict, notes: list[str], *, reason: str) -> VerifierVerdict:
    merged = [*notes, reason]
    try:
        return verdict.model_copy(
            update={
                "decision": "reject",
                "evidence_supports_conclusion": False,
                "followup": None,
                "notes": merged,
            }
        )
    except ValidationError:
        return VerifierVerdict(
            decision="reject",
            evidence_supports_conclusion=False,
            unsupported_claims=list(verdict.unsupported_claims),
            counterexamples=list(verdict.counterexamples),
            remediation_consistent=verdict.remediation_consistent,
            safety_ok=verdict.safety_ok,
            notes=merged,
            confidence=verdict.confidence,
        )
