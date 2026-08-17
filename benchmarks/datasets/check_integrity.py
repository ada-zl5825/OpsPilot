from __future__ import annotations

import json
from pathlib import Path

DATASET_DIR = Path(__file__).parent / "incidents" / "v1"
FORBIDDEN_HINTS = ("ground_truth", "simulated error", "root cause is")


def check_integrity(dataset_dir: Path = DATASET_DIR) -> list[str]:
    errors: list[str] = []
    files = sorted(dataset_dir.glob("*.json"))
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if "ground_truth_root_causes" not in payload:
            errors.append(f"{path.name}: missing ground_truth_root_causes")
        prompt_blob = " ".join(payload.get("prompt_variants", [])).lower()
        for hint in FORBIDDEN_HINTS:
            if hint in prompt_blob:
                errors.append(f"{path.name}: prompt leaks '{hint}'")
        if payload.get("verification_code") and payload["verification_code"] in prompt_blob:
            errors.append(f"{path.name}: verification_code leaked into prompt")
    return errors


def main() -> int:
    errors = check_integrity()
    files = list(DATASET_DIR.glob("*.json"))
    if errors:
        print("dataset integrity failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"dataset integrity ok ({len(files)} scenarios)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
