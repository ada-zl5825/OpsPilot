from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ApprovalDecision(BaseModel):
    proposal_id: UUID
    decision: Literal["approved", "rejected"]
    actor_id: str
    actor_role: str
    reason: str | None = None
    proposal_digest: str
    decided_at: datetime
