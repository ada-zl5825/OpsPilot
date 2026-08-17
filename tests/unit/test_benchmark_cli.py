from pathlib import Path

from benchmarks.cli import main
from pytest import CaptureFixture

from opspilot.cli import main as opspilot_main


def test_dry_run_lists_eval_variants(capsys: CaptureFixture[str]) -> None:
    assert main(["--dry-run", "--split", "eval"]) == 0
    output = capsys.readouterr().out
    assert "S01-V01" in output
    assert "S01-V05" not in output
    assert "integrity_ok" in output


def test_opspilot_benchmark_dry_run(capsys: CaptureFixture[str]) -> None:
    assert opspilot_main(["benchmark", "--dry-run"]) == 0
    assert "S01-V01" in capsys.readouterr().out


def test_offline_writes_json_and_markdown(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    assert main(["--offline", "--split", "eval", "--out", str(tmp_path)]) == 0
    capsys.readouterr()
    reports = list(tmp_path.glob("*/report.json"))
    markdown = list(tmp_path.glob("*/report.md"))
    assert reports and markdown
    text = markdown[0].read_text(encoding="utf-8")
    assert "deterministic" in text
    assert "single_agent" in text
    assert "unsafe_action" in text
