from __future__ import annotations

from typing import Any

import httpx

from opspilot.settings import Settings


class HolmesClient:
    """HTTP client for the pinned HolmesGPT container. Implemented in Phase 0."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client

    async def ask(self, prompt: str, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        _ = prompt, extra
        raise NotImplementedError("Phase 0: HolmesGPT ask integration is not implemented")
