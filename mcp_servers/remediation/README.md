# Remediation MCP

Phase 4. Agent-visible tools create proposals or perform read-only dry-run / verify.

Registered on Holmes: `propose_*`, `dry_run_remediation`, `verify_recovery`, plus capability/snapshot reads.

`execute_approved_proposal` and `rollback_execution` are control-plane only. They are not registered on this FastMCP server and must not appear in the HolmesGPT Agent tool catalog.
