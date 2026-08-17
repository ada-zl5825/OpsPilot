from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"
DENIED_PATH_PARTS = (".env", "kubeconfig", "secrets", ".pem", "id_rsa")
ALLOWED_PREFIXES = ("simulator/", "src/", "deploy/", "charts/")


def load_json(name: str) -> dict[str, Any]:
    return _load(DATA_DIR / name)


@lru_cache(maxsize=8)
def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must be a JSON object")
    return payload


def is_readable_path(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    if any(part in lowered for part in DENIED_PATH_PARTS):
        return False
    return any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES)
