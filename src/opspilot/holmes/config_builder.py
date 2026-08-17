from __future__ import annotations

from typing import Any

from opspilot.settings import Settings

PINNED_HOLMES_IMAGE = "robustadev/holmes:0.39.0"
PINNED_HOLMES_PORT = 5050


def build_holmes_runtime_config(settings: Settings) -> dict[str, Any]:
    """Container-level Holmes config. Source stays out of this repository."""
    if settings.holmes_image != PINNED_HOLMES_IMAGE:
        raise ValueError(f"Holmes image must be pinned to {PINNED_HOLMES_IMAGE}")
    return {
        "image": settings.holmes_image,
        "version": settings.holmes_version,
        "base_url": settings.holmes_base_url,
        "model_provider": "azure_openai",
        "model": settings.holmes_model,
        "http_port": PINNED_HOLMES_PORT,
        "mcp_server": "opspilot_lab",
    }
