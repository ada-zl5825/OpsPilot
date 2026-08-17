from __future__ import annotations

from collections.abc import Iterable

from opspilot.domain.incidents import DiagnosisRubric, IncidentScenario

FORBIDDEN_PROMPT_HINTS = (
    "ground_truth",
    "simulated error",
    "root cause is",
    "verification_code",
    "pool exhaust",
    "connection pool",
    "cache collapse",
    "bad deploy",
    "wrong version",
    "payment timeout",
    "injected fault",
    "fault injection",
)


_GENERIC_RUBRIC_TOKENS = frozenset(
    {
        "checkout",
        "redis",
        "cache",
        "payment",
        "release",
        "pool",
        "latency",
        "database",
        "downstream",
        "deadline",
        "regression",
    }
)


def scorer_only_strings(scenario: IncidentScenario) -> list[str]:
    values: list[str] = []
    values.extend(scenario.ground_truth_root_causes)
    if scenario.verification_code:
        values.append(scenario.verification_code)
    values.extend(item.description for item in scenario.required_evidence)
    values.extend(item.description for item in scenario.allowed_remediations)
    values.extend(item.description for item in scenario.recovery_checks)
    values.extend(scenario.forbidden_shortcuts)
    values.extend(scenario.distractors)
    values.extend(rubric_leak_strings(scenario.diagnosis_rubric))
    return [item for item in values if item]


def rubric_leak_strings(rubric: DiagnosisRubric | None) -> list[str]:
    if rubric is None:
        return []
    candidates = [rubric.fault_kind, *rubric.accept_any, *rubric.reject_if_primary]
    candidates.extend(rubric.entity_aliases)
    for checkpoint in rubric.evidence_checkpoints:
        candidates.extend(checkpoint.must_match)
    leaks: list[str] = []
    for item in candidates:
        if not item or item.lower() in _GENERIC_RUBRIC_TOKENS:
            continue
        leaks.append(item)
    return leaks


def find_ground_truth_leaks(text: str, scenario: IncidentScenario) -> list[str]:
    leaks: list[str] = []
    for value in scorer_only_strings(scenario):
        if value and value in text:
            leaks.append(value)
    lowered = text.lower()
    for hint in FORBIDDEN_PROMPT_HINTS:
        if hint in lowered:
            leaks.append(hint)
    return leaks


def assert_no_ground_truth(text: str, scenario: IncidentScenario) -> None:
    leaks = find_ground_truth_leaks(text, scenario)
    if leaks:
        raise ValueError(f"ground truth leaked into agent text: {leaks[:5]}")


def assert_agent_text_is_safe(text: str, extra_forbidden: Iterable[str] = ()) -> None:
    lowered = text.lower()
    for hint in FORBIDDEN_PROMPT_HINTS:
        if hint in lowered:
            raise ValueError(f"agent text contains forbidden hint: {hint}")
    for value in extra_forbidden:
        if value and value in text:
            raise ValueError("agent text contains scorer-only value")
