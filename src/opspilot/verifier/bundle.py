from __future__ import annotations

from collections.abc import Sequence

from opspilot.domain.evidence import Evidence, Hypothesis
from opspilot.investigation.budget import BudgetState, ToolBudget
from opspilot.investigation.diagnosis import DiagnosisDraft, HypothesisDraft
from opspilot.investigation.prompt import AgentVisibleIncident
from opspilot.investigation.runner import InvestigationResult
from opspilot.verifier.budget import investigator_steps_used, snapshot_budget
from opspilot.verifier.schema import EvidenceBundleItem, InvestigatorBundle


def evidence_items(evidence: Sequence[Evidence]) -> list[EvidenceBundleItem]:
    return [
        EvidenceBundleItem(
            evidence_id=str(item.evidence_id),
            source_tool=item.source_tool,
            source_system=item.source_system,
            query_fingerprint=item.query_fingerprint,
            summary=item.summary,
        )
        for item in evidence
    ]


def hypothesis_drafts(hypotheses: Sequence[Hypothesis]) -> list[HypothesisDraft]:
    return [
        HypothesisDraft(
            hypothesis_id=item.hypothesis_id,
            statement=item.statement,
            confidence=item.confidence,
            status=item.status,
            supporting_evidence_ids=[str(value) for value in item.supporting_evidence_ids],
            contradicting_evidence_ids=[str(value) for value in item.contradicting_evidence_ids],
        )
        for item in hypotheses
    ]


def diagnosis_from_result(result: InvestigationResult) -> DiagnosisDraft | None:
    if result.parsed.draft is not None:
        return result.parsed.draft
    diagnosis = result.run.final_diagnosis
    if diagnosis is None:
        return None
    return DiagnosisDraft(
        root_cause=diagnosis.root_cause,
        evidence_ids=[str(item) for item in diagnosis.evidence_ids],
        rejected_hypotheses=list(diagnosis.rejected_hypotheses),
        confidence=diagnosis.confidence,
        uncertainties=list(diagnosis.uncertainties),
        recommended_actions=list(diagnosis.recommended_actions),
        hypotheses=hypothesis_drafts(result.hypotheses),
    )


def build_bundle(
    *,
    visible: AgentVisibleIncident,
    result: InvestigationResult,
    budget: ToolBudget,
    budget_state: BudgetState | None = None,
    followups_used: int = 0,
    evidence: Sequence[Evidence] | None = None,
    hypotheses: Sequence[Hypothesis] | None = None,
) -> InvestigatorBundle:
    collected = list(evidence if evidence is not None else result.evidence)
    hyps = list(hypotheses if hypotheses is not None else result.hypotheses)
    state = budget_state or result.budget
    steps = investigator_steps_used(result.events)
    draft = diagnosis_from_result(result)
    snapshot = snapshot_budget(
        state,
        budget,
        followups_used=followups_used,
        steps_used=steps,
    )
    return InvestigatorBundle(
        scenario_id=visible.scenario_id,
        incident=visible,
        diagnosis=draft,
        evidence=evidence_items(collected),
        hypotheses=hypothesis_drafts(hyps) if hyps else list(draft.hypotheses) if draft else [],
        recommended_actions=list(draft.recommended_actions) if draft else [],
        rejected_hypotheses=list(draft.rejected_hypotheses) if draft else [],
        uncertainties=list(draft.uncertainties) if draft else [],
        budget=snapshot,
        followup_used=followups_used > 0,
    )
