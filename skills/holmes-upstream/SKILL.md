---
name: holmes-upstream
description: Integrate and pin HolmesGPT as an external container runtime, parse stream events, and prepare small upstream PRs. Use when changing Holmes client, image pin, stream parser, Azure compatibility, DCO, or holmesgpt fork work.
---

# HolmesGPT upstream

HolmesGPT is the Agent runtime. OpsPilot talks to it over HTTP/container. Do not copy HolmesGPT source into this repository.

## Pin

- Image: `robustadev/holmes:0.39.0`
- Tag file: `config/holmesgpt.pin`
- Reject `:latest` and unpinned digests
- Upgrade only after contract tests in `src/opspilot/holmes/compatibility.py` plus stream/approval smoke

## Phase 0 work (done 2026-08-17)

Do not redo this unless the pin or compose contract breaks. See `docs/HANDOFF.md`.

1. Run Holmes in Compose (`make holmes-up`) — image entrypoint is CLI; Compose must use `python -u server.py`. Mount config to `/root/.holmes/config.yaml` (0.39.0 does not honor `HOLMES_CONFIG_PATH`).
2. Call Azure OpenAI through Holmes, one builtin read-only toolset (`internet`) plus `opspilot_lab`
3. Call `lab_status` / `lab_echo`
4. Capture stream events: LLM turn, tool call, tool result, approval, token usage, final answer
5. Prove `approval_required_tools` blocks `lab_mutate_probe` and that OpsPilot never auto-approves
6. Keep `docs/UPSTREAM_BASELINE.md` current with pin, digest, tests, and residual risks
7. Never add `health_check_tool` to the 0.39.0 MCP toolset config; it is rejected and drops `opspilot_lab`

## Code map

- `src/opspilot/holmes/client.py` — HTTP client
- `src/opspilot/holmes/stream_parser.py` — normalize Holmes events to `AgentEvent`
- `src/opspilot/holmes/config_builder.py` — pin enforcement
- `src/opspilot/holmes/compatibility.py` — Azure tool schema gate

## Upstream PR rules

- Fork is only for small, upstreamable branches. Do not pile OpsPilot domain models onto fork `master`
- One problem per PR. Tests first. DCO `Signed-off-by` required
- Use `skills/upstream-pr/SKILL.md` for the PR loop

## Out of scope

Simulator, UI, remediation execute path, Multi-Agent, SFT.
