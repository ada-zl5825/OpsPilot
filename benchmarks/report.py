from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path

from opspilot.eval.constants import BENCHMARK_VERSION
from opspilot.eval.models import (
    AggregateMetrics,
    BenchmarkReport,
    ConditionSummary,
    ScoreCard,
)
from opspilot.investigation.constants import PROMPT_VERSION, TOOL_CATALOG_VERSION


def _aggregate(values: Sequence[float]) -> AggregateMetrics:
    if not values:
        return AggregateMetrics(count=0, mean=0.0, median=0.0, stddev=0.0, min=0.0, max=0.0)
    std = statistics.pstdev(values) if len(values) > 1 else 0.0
    return AggregateMetrics(
        count=len(values),
        mean=round(statistics.mean(values), 4),
        median=round(statistics.median(values), 4),
        stddev=round(std, 4),
        min=round(min(values), 4),
        max=round(max(values), 4),
    )


def summarize(cards: Sequence[ScoreCard], *, split: str) -> list[ConditionSummary]:
    grouped: dict[str, list[ScoreCard]] = defaultdict(list)
    for card in cards:
        grouped[card.condition].append(card)
    summaries: list[ConditionSummary] = []
    for condition, group in sorted(grouped.items()):
        by_diff: dict[str, list[float]] = defaultdict(list)
        classes: Counter[str] = Counter()
        for card in group:
            by_diff[card.difficulty].append(card.composite)
            classes.update(card.failure_classes)
        summaries.append(
            ConditionSummary(
                condition=condition,
                split=split,
                n=len(group),
                composite=_aggregate([card.composite for card in group]),
                root_cause_score=_aggregate([card.raw.root_cause_score for card in group]),
                evidence_coverage=_aggregate([card.raw.evidence_coverage for card in group]),
                tool_efficiency=_aggregate([card.raw.tool_efficiency for card in group]),
                recovery_success=_aggregate([card.raw.recovery_success for card in group]),
                failure_recovery=_aggregate([card.raw.failure_recovery for card in group]),
                escalation_accuracy=_aggregate([card.raw.escalation_accuracy for card in group]),
                unsafe_action_rate=round(
                    sum(card.raw.unsafe_action_rate for card in group) / len(group), 4
                ),
                unapproved_write_count=sum(card.raw.unapproved_write_count for card in group),
                hard_fail_count=sum(1 for card in group if card.hard_fails),
                failure_class_counts=dict(classes),
                by_difficulty={
                    key: round(statistics.mean(vals), 4) for key, vals in by_diff.items()
                },
            )
        )
    return summaries


def build_report(
    cards: Sequence[ScoreCard],
    *,
    split: str,
    conditions: Sequence[str],
    gate_passed: bool | None = None,
    gate_failures: Sequence[str] = (),
) -> BenchmarkReport:
    return BenchmarkReport(
        benchmark_version=BENCHMARK_VERSION,
        prompt_version=PROMPT_VERSION,
        tool_catalog_version=TOOL_CATALOG_VERSION,
        split=split,
        conditions=list(conditions),
        cards=list(cards),
        summaries=summarize(cards, split=split),
        gate_passed=gate_passed,
        gate_failures=list(gate_failures),
    )


def render_markdown(report: BenchmarkReport) -> str:
    lines = [
        f"# OpsPilot Benchmark {report.benchmark_version}",
        "",
        f"- Prompt: `{report.prompt_version}`",
        f"- Tool catalog: `{report.tool_catalog_version}`",
        f"- Split: `{report.split}`",
        f"- Conditions: {', '.join(report.conditions)}",
        "",
        "Composite score is ranking-only. Raw metrics are reported separately.",
        "`unsafe_action` or an unapproved write forces composite = 0.",
        "",
        "## Summaries",
        "",
        "| Condition | N | Composite | Root cause | Evidence | Tool eff. "
        "| Recovery | Fail rec. | Escalation | Unsafe | Hard fails |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report.summaries:
        row = (
            f"| {item.condition} | {item.n} | {item.composite.mean:.3f} | "
            f"{item.root_cause_score.mean:.3f} | {item.evidence_coverage.mean:.3f} | "
            f"{item.tool_efficiency.mean:.3f} | {item.recovery_success.mean:.3f} | "
            f"{item.failure_recovery.mean:.3f} | {item.escalation_accuracy.mean:.3f} | "
            f"{item.unsafe_action_rate:.3f} | {item.hard_fail_count} |"
        )
        lines.append(row)
    lines.extend(["", "## Failure classes", ""])
    for item in report.summaries:
        if not item.failure_class_counts:
            lines.append(f"- `{item.condition}`: none")
            continue
        listed = ", ".join(
            f"{name}={count}" for name, count in sorted(item.failure_class_counts.items())
        )
        lines.append(f"- `{item.condition}`: {listed}")
    if report.gate_passed is not None:
        lines.extend(["", "## Regression gate", ""])
        lines.append("PASS" if report.gate_passed else "FAIL")
        for failure in report.gate_failures:
            lines.append(f"- {failure}")
    lines.extend(["", "## Per-variant scores", ""])
    lines.append("| Variant | Condition | Split | Composite | Hard fails |")
    lines.append("|---|---|---|---:|---|")
    for card in report.cards:
        fails = ",".join(card.hard_fails) if card.hard_fails else ""
        lines.append(
            f"| {card.variant_id} | {card.condition} | {card.split} | "
            f"{card.composite:.3f} | {fails} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_report(report: BenchmarkReport, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def nearly_equal(left: float, right: float, *, tol: float = 1e-3) -> bool:
    return math.isclose(left, right, abs_tol=tol, rel_tol=0.0)
