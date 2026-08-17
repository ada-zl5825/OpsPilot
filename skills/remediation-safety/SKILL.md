---
name: remediation-safety
description: Implement Proposal, policy, digest-bound approval, idempotent execution, recovery verification, and rollback. Use when changing policy, executor, approval routes, or write-path security tests.
---

# Remediation safety

LLM may propose actions. It has no write permission. Writes are executed only by the deterministic control plane.

## Path

```text
Proposal → Policy → Dry Run → Human Approval → Idempotent Execute → Verify → Rollback
```

## Rules

- Agent tools: `propose_*`, `dry_run_remediation`, `verify_recovery` only
- Control plane only: `execute_approved_proposal`, `rollback_execution`
- Approval binds `proposal_digest`. Any parameter change voids the approval
- Expired proposals cannot execute
- Same proposal succeeds at most once (`idempotency_key`)
- Approver cannot be the system Agent
- Reject cannot be auto-overridden
- Typed actions only: rollback, restart, scale (config update later). No raw shell
- Namespace/service allowlist. Block `--token`, `--kubeconfig`, `--as`

## Code map

- `src/opspilot/policy/` — rules, risk, redaction
- `src/opspilot/executor/` — typed execute, digest, rollback
- `src/opspilot/api/routes_approvals.py` — approve/reject/execute
- `src/opspilot/verification/` — recovery checks

## Required security tests

Shell metacharacters, flag injection, proposal tampering, expired approval, replay, cross-namespace write, direct MCP write bypass, concurrent approval race.

Any unapproved write is a failed test.
