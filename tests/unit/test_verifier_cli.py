from pathlib import Path

from benchmarks.cli import main as benchmark_main
from experiments.single_vs_verifier.__main__ import main as experiment_main
from pytest import CaptureFixture

from opspilot.cli import main


def test_verify_prompt_only_s01_s04(capsys: CaptureFixture[str]) -> None:
    assert main(["verify", "--all", "--prompt-only"]) == 0
    output = capsys.readouterr().out
    for scenario_id in ("S01", "S02", "S03", "S04"):
        assert f"## {scenario_id} verifier" in output
        assert f"## {scenario_id} followup" in output
    assert "checkout_database_connection_pool_exhausted" not in output
    assert "OP-S01-M4QX7C" not in output
    assert "phase6-verifier-v1" in output


def test_experiment_offline_writes_json_and_markdown(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    assert experiment_main(["--offline", "--out", str(tmp_path)]) == 0
    capsys.readouterr()
    assert list(tmp_path.glob("*/report.json"))
    markdown = next(tmp_path.glob("*/report.md")).read_text(encoding="utf-8")
    assert "Single-Agent vs Verifier" in markdown
    assert "DO NOT PROMOTE" in markdown


def test_benchmark_cli_accepts_verifier_condition(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    assert (
        benchmark_main(
            [
                "--offline",
                "--split",
                "eval",
                "--condition",
                "single_agent",
                "--condition",
                "verifier",
                "--out",
                str(tmp_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    text = next(tmp_path.glob("*/report.md")).read_text(encoding="utf-8")
    assert "single_agent" in text
    assert "verifier" in text
