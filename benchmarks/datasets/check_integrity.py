from __future__ import annotations

import json
from pathlib import Path

DATASET_DIR = Path(__file__).parent / "incidents" / "v1"
REQUIRED_IDS = {"S01", "S02", "S03", "S04"}
REQUIRED_FIELDS = (
    "scenario_id",
    "version",
    "title",
    "difficulty",
    "initial_symptoms",
    "ground_truth_root_causes",
    "required_evidence",
    "necessary_tool_categories",
    "forbidden_shortcuts",
    "allowed_remediations",
    "recovery_checks",
    "distractors",
    "prompt_variants",
    "verification_code",
)
AGENT_TEXT_FIELDS = (
    "title",
    "initial_symptoms",
    "prompt_variants",
    "distractors",
    "forbidden_shortcuts",
)
FORBIDDEN_HINTS = (
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


def _agent_text(payload: dict[str, object]) -> str:
    chunks: list[str] = []
    for field in AGENT_TEXT_FIELDS:
        value = payload.get(field, "")
        if isinstance(value, list):
            chunks.extend(str(item) for item in value)
        else:
            chunks.append(str(value))
    return " ".join(chunks).lower()


def check_integrity(dataset_dir: Path = DATASET_DIR) -> list[str]:
    errors: list[str] = []
    files = sorted(dataset_dir.glob("S*.json"))
    seen_ids: set[str] = set()
    seen_codes: set[str] = set()

    if not files:
        errors.append("no scenario files found")
        return errors

    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for field in REQUIRED_FIELDS:
            if field not in payload:
                errors.append(f"{path.name}: missing {field}")
        scenario_id = str(payload.get("scenario_id", ""))
        if scenario_id:
            if scenario_id in seen_ids:
                errors.append(f"{path.name}: duplicate scenario_id {scenario_id}")
            seen_ids.add(scenario_id)
        if not payload.get("ground_truth_root_causes"):
            errors.append(f"{path.name}: missing ground_truth_root_causes")
        if not payload.get("required_evidence"):
            errors.append(f"{path.name}: missing required_evidence")
        if not payload.get("allowed_remediations"):
            errors.append(f"{path.name}: missing allowed_remediations")
        if not payload.get("recovery_checks"):
            errors.append(f"{path.name}: missing recovery_checks")
        code = payload.get("verification_code")
        if not code:
            errors.append(f"{path.name}: missing verification_code")
        elif code in seen_codes:
            errors.append(f"{path.name}: duplicate verification_code")
        else:
            seen_codes.add(str(code))
        agent_blob = _agent_text(payload)
        for hint in FORBIDDEN_HINTS:
            if hint in agent_blob:
                errors.append(f"{path.name}: agent-facing text leaks '{hint}'")
        if code and str(code).lower() in agent_blob:
            errors.append(f"{path.name}: verification_code leaked into agent-facing text")
        for cause in payload.get("ground_truth_root_causes", []):
            if str(cause).lower() in agent_blob:
                errors.append(f"{path.name}: ground truth leaked into agent-facing text")

    missing = REQUIRED_IDS - seen_ids
    if missing:
        errors.append(f"missing required scenarios: {', '.join(sorted(missing))}")
    return errors


def main() -> int:
    errors = check_integrity()
    files = list(DATASET_DIR.glob("S*.json"))
    if errors:
        print("dataset integrity failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"dataset integrity ok ({len(files)} scenarios)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
