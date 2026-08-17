# Deployment MCP

Phase 2 read-only tools. Never return secrets, deploy credentials, or raw GitHub tokens.

| Tool | Permission | Notes |
|---|---|---|
| `get_recent_deployments` | read | Version, time, SHA, status, actor, changed services |
| `compare_deployments` | read | Allowlisted files only; `.env` / kubeconfig omitted |
| `get_ci_failure_summary` | read | Failed steps, redacted error summary, related commit |

Live mode reads lab `/releases` and `/version`. Diffs and CI summaries stay on the local catalog.
