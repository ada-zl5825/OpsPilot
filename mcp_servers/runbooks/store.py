from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=4)
def load_runbooks() -> list[dict[str, Any]]:
    payload = json.loads((DATA_DIR / "catalog.json").read_text(encoding="utf-8"))
    runbooks = payload.get("runbooks", [])
    if not isinstance(runbooks, list):
        raise ValueError("runbooks catalog must be a list")
    return [item for item in runbooks if isinstance(item, dict)]
