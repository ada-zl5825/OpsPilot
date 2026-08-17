from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class ArtifactStore:
    def __init__(self, root: Path | None = None) -> None:
        configured = os.environ.get("OPSPILOT_ARTIFACT_DIR")
        self.root = root or Path(configured or Path.cwd() / ".opspilot-artifacts")
        self.root.mkdir(parents=True, exist_ok=True)

    def spill(self, tool: str, payload: Any) -> str:
        body = json.dumps(payload, default=str, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(body).hexdigest()[:16]
        name = f"{tool}-{digest}.json"
        path = self.root / name
        path.write_bytes(body)
        return f"artifact://{name}"
