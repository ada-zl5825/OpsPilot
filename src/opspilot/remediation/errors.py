from __future__ import annotations


class RemediationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


HTTP_STATUS_BY_CODE: dict[str, int] = {
    "not_found": 404,
    "unapproved_write": 403,
    "digest_mismatch": 403,
    "tampered_proposal": 403,
    "forbidden_actor": 403,
    "policy_denied": 403,
    "cross_namespace": 403,
    "invalid_command": 400,
    "proposal_expired": 409,
    "already_rejected": 409,
    "not_executed": 409,
    "conflict": 409,
}
