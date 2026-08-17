# OpsPilot lab MCP (Phase 0)

Connectivity and approval-gate fixture. Not a production observability server.

| Tool | Permission | Notes |
|---|---|---|
| `lab_status` | read | Connectivity probe. Do **not** set Holmes `health_check_tool` on 0.39.0 — that field is rejected. |
| `lab_echo` | read | MCP round-trip |
| `lab_mutate_probe` | mutate | Listed in `approval_required_tools`; refuses to write |

Holmes config: `config/holmes/config.yaml`.
