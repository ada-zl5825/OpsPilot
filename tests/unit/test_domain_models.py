from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from opspilot.domain import (
    Diagnosis,
    IncidentRun,
    IncidentScenario,
    IncidentStatus,
    RemediationProposal,
)
from opspilot.domain.incidents import EvidenceExpectation, RecoveryCheck, RemediationTemplate
from opspilot.domain.remediation import (
    RemediationActionType,
    ResourceRef,
    RollbackPlan,
)


def test_incident_run_defaults() -> None:
    run = IncidentRun(
        run_id=uuid4(),
        source="manual",
        status=IncidentStatus.INCIDENT_CREATED,
        model="azure/gpt-4o",
        prompt_version="v0",
        tool_catalog_version="v0",
        started_at=datetime.now(UTC),
        estimated_cost=Decimal("0"),
    )
    assert run.final_diagnosis is None
    assert run.token_usage.total_tokens == 0


def test_diagnosis_requires_evidence_ids() -> None:
    evidence_id = uuid4()
    diagnosis = Diagnosis(
        root_cause="connection pool exhaustion",
        evidence_ids=[evidence_id],
        confidence=0.8,
    )
    assert diagnosis.evidence_ids == [evidence_id]


def test_diagnosis_rejects_empty_evidence_ids() -> None:
    with pytest.raises(ValidationError):
        Diagnosis(root_cause="guess", evidence_ids=[], confidence=0.1)


def test_run_cannot_be_resolved_without_recovery_verification() -> None:
    with pytest.raises(ValidationError, match="recovery verification"):
        IncidentRun(
            run_id=uuid4(),
            source="manual",
            status=IncidentStatus.RESOLVED,
            model="azure/gpt-4o",
            prompt_version="v0",
            tool_catalog_version="v0",
            started_at=datetime.now(UTC),
            estimated_cost=Decimal("0"),
        )


def test_diagnosis_complete_requires_final_diagnosis() -> None:
    with pytest.raises(ValidationError, match="final diagnosis"):
        IncidentRun(
            run_id=uuid4(),
            source="manual",
            status=IncidentStatus.DIAGNOSIS_COMPLETE,
            model="azure/gpt-4o",
            prompt_version="v0",
            tool_catalog_version="v0",
            started_at=datetime.now(UTC),
            estimated_cost=Decimal("0"),
        )


def test_scenario_keeps_ground_truth_off_prompt_fields() -> None:
    scenario = IncidentScenario(
        scenario_id="S01",
        version="1",
        title="checkout errors",
        difficulty="L3",
        initial_symptoms=["checkout 5xx rising"],
        ground_truth_root_causes=["db_pool_exhausted"],
        required_evidence=[
            EvidenceExpectation(source_system="prometheus", description="pool usage")
        ],
        necessary_tool_categories={"metrics", "logs"},
        forbidden_shortcuts=["guess from service name"],
        allowed_remediations=[
            RemediationTemplate(action_type="update_config", description="pool size")
        ],
        recovery_checks=[
            RecoveryCheck(
                check_id="c1",
                description="5xx recovered",
                metric_or_endpoint="checkout_5xx_rate",
                success_criteria="<0.01",
            )
        ],
        distractors=["recent unrelated deploy"],
        prompt_variants=["checkout 5xx increased in the last 15 minutes"],
        verification_code="OP-S01-VERIFY",
    )
    prompt = " ".join(scenario.prompt_variants)
    assert scenario.ground_truth_root_causes[0] not in prompt
    assert scenario.verification_code not in prompt


def test_proposal_typed_action() -> None:
    target = ResourceRef(kind="Deployment", name="checkout", namespace="lab")
    proposal = RemediationProposal(
        proposal_id=uuid4(),
        incident_run_id=uuid4(),
        action_type=RemediationActionType.ROLLBACK_DEPLOYMENT,
        target=target,
        rationale="error rate rose after deploy",
        expected_effect="5xx returns to baseline",
        risk_level="high",
        rollback_plan=RollbackPlan(
            action_type=RemediationActionType.ROLLBACK_DEPLOYMENT, target=target
        ),
        idempotency_key="abc",
        expires_at=datetime.now(UTC),
    )
    assert proposal.action_type is RemediationActionType.ROLLBACK_DEPLOYMENT
