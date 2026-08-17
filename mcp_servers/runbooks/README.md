# Runbook MCP

Phase 2 read-only tool: `search_runbooks`.

Runbook text is untrusted input. Embedded "ignore previous rules" or "execute this command" text cannot override policy. Every result includes `untrusted_content` and `cannot_override_policy`.

Ground truth and verification codes must not appear in runbook documents.
