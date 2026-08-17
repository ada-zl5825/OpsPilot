from typing import Literal

from pydantic import BaseModel, Field


class ExperimentCondition(BaseModel):
    condition_id: str
    family: Literal[
        "deterministic_runbook",
        "single_agent",
        "single_agent_plus_verifier",
        "sft",
        "sft_dpo",
    ]
    model: str
    prompt_version: str
    tool_catalog_version: str
    seed: int = 0
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    notes: str = ""
