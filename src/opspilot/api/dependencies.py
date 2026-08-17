from functools import lru_cache
from pathlib import Path

from opspilot.investigation.store import (
    InMemoryInvestigationStore,
    InvestigationStore,
    JsonlInvestigationStore,
)
from opspilot.settings import Settings, get_settings


def settings() -> Settings:
    return get_settings()


@lru_cache(maxsize=1)
def investigation_store() -> InvestigationStore:
    configured = get_settings().investigation_artifact_dir
    if configured:
        return JsonlInvestigationStore(Path(configured))
    return InMemoryInvestigationStore()
