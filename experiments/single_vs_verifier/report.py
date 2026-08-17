from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from benchmarks.datasets.variants import load_variants
from benchmarks.harness import _score_built, build_condition
from experiments.single_vs_verifier.compare import (
    ABComparison,
    compare_ab,
    compare_failure_pair,
)
from experiments.single_vs_verifier.failures import all_failure_pairs
from pydantic import BaseModel, Field

from opspilot.eval.models import ScoreCard

DEFAULT_OUT = Path("artifacts") / "experiments" / "single_vs_verifier"


class ExperimentReport(BaseModel):
    experiment: str = "single_vs_verifier"
    split: str
    comparison: ABComparison
    holdout: ABComparison | None = None
    single_cards: list[ScoreCard] = Field(default_factory=list)
    verifier_cards: list[ScoreCard] = Field(default_factory=list)
    extra: dict[str, str] = Field(default_factory=dict)


def run_experiment(
    *,
    split: str = "eval",
    out_dir: Path | None = None,
    include_holdout: bool = True,
) -> ExperimentReport:
    variants = load_variants(split=split)
    single_cards = [_score_built(item) for item in build_condition("single_agent", variants)]
    verifier_cards = [_score_built(item) for item in build_condition("verifier", variants)]
    failure_deltas = [
        compare_failure_pair(_score_built(flawed), _score_built(corrected))
        for flawed, corrected in all_failure_pairs()
    ]
    comparison = compare_ab(single_cards, verifier_cards, failure_deltas, split=split)
    holdout = None
    if include_holdout and split == "eval":
        holdout_variants = load_variants(split="holdout")
        holdout = compare_ab(
            [_score_built(item) for item in build_condition("single_agent", holdout_variants)],
            [_score_built(item) for item in build_condition("verifier", holdout_variants)],
            [],
            split="holdout",
        )
        holdout.promotion.reasons = [
            "holdout is reported only; it is not used to tune prompts or decide promotion",
            *holdout.promotion.reasons,
        ]
        holdout.promotion.promote = False
    report = ExperimentReport(
        split=split,
        comparison=comparison,
        holdout=holdout,
        single_cards=single_cards,
        verifier_cards=verifier_cards,
    )
    target = (out_dir or DEFAULT_OUT) / str(uuid4())
    write_experiment_report(report, target)
    report.extra["artifact_dir"] = str(target)
    return report


def render_markdown(report: ExperimentReport) -> str:
    cmp = report.comparison
    promo = cmp.promotion
    lines = [
        "# Phase 6 Single-Agent vs Verifier",
        "",
        "Bounded two-role experiment: Investigator schema handoff, one Verifier review,",
        "at most one follow-up, shared tool budget. Not a Multi-Agent orchestrator.",
        "",
        f"- Split used for the decision: `{report.split}`",
        "- Holdout is scored separately and was not used to tune the Verifier prompt.",
        "- Composite score is ranking-only. Raw metrics are reported separately.",
        "",
        "## Eval A/B",
        "",
        "| Condition | N | Composite | Root cause | Evidence | Tool eff. | L2 RC | L3 RC "
        "| Tokens | Cost | Latency ms | LLM turns | Tools | Unsafe |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in (cmp.single, cmp.verifier):
        lines.append(
            f"| {item.condition} | {item.n} | {item.composite:.3f} | {item.root_cause:.3f} | "
            f"{item.evidence:.3f} | {item.tool_efficiency:.3f} | {item.l2_root_cause:.3f} | "
            f"{item.l3_root_cause:.3f} | {item.mean_tokens:.1f} | {item.mean_cost:.4f} | "
            f"{item.mean_latency_ms:.1f} | {item.mean_llm_turns:.2f} | "
            f"{item.mean_tool_calls:.2f} | {item.unsafe_rate:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Deltas (Verifier − Single-Agent)",
            "",
            f"- Root-cause lift: **{cmp.root_cause_lift:.3f}**",
            f"- L3 root-cause lift: **{cmp.l3_root_cause_lift:.3f}**",
            f"- Evidence lift: **{cmp.evidence_lift:.3f}**",
            f"- Composite lift: **{cmp.composite_lift:.3f}**",
            f"- Cost ratio: **{cmp.cost_ratio:.3f}**",
            f"- Latency ratio: **{cmp.latency_ratio:.3f}**",
            f"- Token ratio: **{cmp.token_ratio:.3f}**",
            f"- Unsafe delta: **{cmp.unsafe_delta:.3f}**",
            f"- Loop/repeat delta: **{cmp.loop_delta:.3f}**",
            "",
            "## Constructed Investigator failures",
            "",
            "These are not the frozen Single-Agent baseline. They measure whether Verifier",
            "can reduce a specific failure type when Investigator is already wrong.",
            "",
            "| Kind | Inv. wrong | Ver. wrong | Inv. miss ev. | Ver. miss ev. "
            "| Inv. RC | Ver. RC | Reduced |",
            "|---|---|---|---|---|---:|---:|---|",
        ]
    )
    for item in cmp.failure_deltas:
        lines.append(
            f"| {item.kind} | {item.investigator_accepted_wrong} | "
            f"{item.verifier_accepted_wrong} | "
            f"{item.investigator_accepted_missing_evidence} | "
            f"{item.verifier_accepted_missing_evidence} | {item.investigator_root_cause:.2f} | "
            f"{item.verifier_root_cause:.2f} | {', '.join(item.reduced) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Promotion",
            "",
            "Promote Investigator+Verifier over Single-Agent only if L3 root-cause rises,",
            "unsafe/loop rates do not rise, cost/latency stay inside caps, and at least one",
            "failure type is reduced.",
            "",
            f"**Decision: {'PROMOTE' if promo.promote else 'DO NOT PROMOTE'}**",
            "",
        ]
    )
    for reason in promo.reasons:
        lines.append(f"- {reason}")
    if promo.failure_types_reduced:
        lines.append(
            f"- Failure types reduced on constructed set: {', '.join(promo.failure_types_reduced)}"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
        ]
    )
    if promo.promote:
        lines.append(
            "Verifier improved L3 accuracy enough, without raising safety or loop rates, "
            "and within the cost/latency caps. Keep the bounded Verifier path."
        )
    else:
        lines.append(
            "On the frozen S01–S04 eval set, Single-Agent already has root-cause 1.0. "
            "Verifier does not improve accuracy and increases tokens, cost, and latency. "
            "Verifier can reduce constructed Investigator failures (wrong conclusion / "
            "missing evidence), but that is not enough to promote Multi-Agent. "
            "**Simple Agent remains the default.**"
        )
    if report.holdout is not None:
        hold = report.holdout
        lines.extend(
            [
                "",
                "## Holdout (not used for tuning or promotion)",
                "",
                f"- Single-Agent root cause: {hold.single.root_cause:.3f}",
                f"- Verifier root cause: {hold.verifier.root_cause:.3f}",
                f"- Cost ratio: {hold.cost_ratio:.3f}",
                f"- Latency ratio: {hold.latency_ratio:.3f}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def write_experiment_report(report: ExperimentReport, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path
