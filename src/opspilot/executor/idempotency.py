from __future__ import annotations

import hashlib
import json
from typing import Any

from opspilot.domain.remediation import RemediationProposal


def digest_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def proposal_digest(proposal: RemediationProposal) -> str:
    """Immutable digest of the action that would be executed.

    Rationale and risk text are excluded so wording edits cannot rebind an
    approval. Any target or parameter change produces a new digest.
    """
    return digest_payload(
        {
            "proposal_id": str(proposal.proposal_id),
            "incident_run_id": str(proposal.incident_run_id),
            "action_type": proposal.action_type.value,
            "target": proposal.target.model_dump(mode="json"),
            "parameters": proposal.parameters,
            "rollback_plan": proposal.rollback_plan.model_dump(mode="json"),
            "idempotency_key": proposal.idempotency_key,
        }
    )
