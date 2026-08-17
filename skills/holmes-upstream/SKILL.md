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

## Phase 0 work

1. Run Holmes in Compose (`docker compose --profile holmes up`)
2. Call Azure OpenAI through Holmes, one builtin read-only toolset
3. Call one custom MCP tool
4. Capture stream events: LLM turn, tool call, tool result, approval, token usage, final answer
5. Prove `approval_required_tools` blocks unapproved execution
6. Write `docs/UPSTREAM_BASELINE.md` with the exact tag, passing tests, and residual risks

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
