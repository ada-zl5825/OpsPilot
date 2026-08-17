from pytest import CaptureFixture

from opspilot.cli import main


def test_health_reports_phase6(capsys: CaptureFixture[str]) -> None:
    assert main(["health"]) == 0
    output = capsys.readouterr().out
    assert '"phase": "6"' in output
    assert "phase6-verifier-v1" in output


def test_investigate_prompt_only_s01_s04(capsys: CaptureFixture[str]) -> None:
    assert main(["investigate", "--all", "--prompt-only"]) == 0
    output = capsys.readouterr().out
    for scenario_id in ("S01", "S02", "S03", "S04"):
        assert f"## {scenario_id}" in output
    assert "checkout_database_connection_pool_exhausted" not in output
    assert "OP-S01-M4QX7C" not in output
    assert "execute_approved_proposal" not in output
