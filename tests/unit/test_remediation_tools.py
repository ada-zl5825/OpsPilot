from uuid import uuid4

from mcp_servers.remediation.tools import (
    dry_run_remediation,
    get_remediation_capabilities,
    propose_restart_workload,
    propose_scale_workload,
    propose_update_config,
    verify_recovery,
)

from opspilot.remediation.service import ControlPlane


def test_capabilities_hide_mutate_tools() -> None:
    result = get_remediation_capabilities({})
    assert result["ok"] is True
    assert result["mutate_tools_agent_visible"] is False
    assert result["control_plane_only_count"] == 2
    assert "execute_approved_proposal" not in result["agent_visible_tools"]
    assert "rollback_execution" not in result["agent_visible_tools"]
    dumped = str(result)
    assert "execute_approved_proposal" not in dumped
    assert "rollback_execution" not in dumped


def test_propose_does_not_write() -> None:
    plane = ControlPlane()
    result = propose_restart_workload(
        {
            "incident_run_id": str(uuid4()),
            "service": "checkout",
            "rationale": "restart after elevated 5xx",
            "expected_effect": "checkout recovers",
        },
        plane=plane,
    )
    assert result["ok"] is True
    assert result["write_performed"] is False
    assert result["executed"] is False
    assert plane.write_count() == 0
    dry = dry_run_remediation({"proposal_id": result["proposal_id"]}, plane=plane)
    assert dry["allowed"] is True
    assert plane.write_count() == 0


def test_scale_and_update_config_tools() -> None:
    plane = ControlPlane()
    scaled = propose_scale_workload(
        {
            "incident_run_id": str(uuid4()),
            "service": "payment",
            "rationale": "add capacity during checkout surge",
            "expected_effect": "p95 returns to baseline",
            "replicas": 3,
        },
        plane=plane,
    )
    assert scaled["ok"] is True
    assert scaled["status"] == "awaiting_approval"
    blocked = propose_update_config(
        {
            "incident_run_id": str(uuid4()),
            "service": "checkout",
            "rationale": "raise pool size after saturation",
            "expected_effect": "503s stop",
            "key": "DB_POOL_MAX",
            "value": "20",
        },
        plane=plane,
    )
    assert blocked["ok"] is True
    assert blocked["policy_allowed"] is False
    assert plane.write_count() == 0


def test_verify_recovery_is_read_only() -> None:
    plane = ControlPlane()
    plane.cluster.inject_fault("checkout")
    failed = verify_recovery({"service": "checkout"}, plane=plane)
    assert failed["ok"] is True
    assert failed["passed"] is False
    recovered = verify_recovery({"service": "payment"}, plane=plane)
    assert recovered["passed"] is True
    assert plane.write_count() == 0
