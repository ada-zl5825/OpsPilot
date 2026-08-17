# OpsPilot Incident Lab — Agent Rules

HolmesGPT is the Agent runtime. This repository owns the incident lab, MCP tools, policy/approval control plane, and trajectory benchmark. Do not copy HolmesGPT source into this repo.

## Hard constraints

1. HolmesGPT is an external upstream dependency, do not copy its source into this repository.
2. All write operations must go through Proposal → Policy → Approval → Executor.
3. The Agent must never receive the `execute_approved_proposal` tool.
4. Do not accept arbitrary Shell strings; actions must be typed commands.
5. Every MCP Tool must have timeout, size limit, structured error, and a contract test.
6. Ground truth must not enter Agent prompt, tool result, or runbook.
7. Benchmarks must not use resource names, logs, or prompts that hint at the answer.
8. Do not share mutable auth state across async requests.
9. Do not log tokens, secrets, kubeconfig, or full sensitive logs on the runtime path.
10. New features must update tests, docs, and benchmark (when applicable) in the same change.
11. Do not introduce Multi-Agent unless the Single-Agent baseline is frozen.
12. Do not introduce SFT/DPO unless the trajectory dataset and benchmark are frozen.

## Current phase

Phase 0 and Phase 1 are complete (`docs/UPSTREAM_BASELINE.md`, `docs/HANDOFF.md`). Next is Phase 2 observability/deployment/runbook MCP. Do not start UI, remediation execution, Multi-Agent, or SFT.

## Skills

Load the matching skill before implementing in that area:

| Skill | Path | Use when |
|---|---|---|
| holmes-upstream | `skills/holmes-upstream/SKILL.md` | HolmesGPT pin, container integration, stream events, DCO, small upstream PRs |
| mcp-toolset | `skills/mcp-toolset/SKILL.md` | MCP servers, tool schema, Azure compatibility, contract tests |
| incident-scenario | `skills/incident-scenario/SKILL.md` | Simulator services, fault injection, ground truth, recovery checks |
| agent-eval | `skills/agent-eval/SKILL.md` | Benchmark harness, scorers, baselines, regression gates |
| remediation-safety | `skills/remediation-safety/SKILL.md` | Proposal, policy, approval, idempotent executor, rollback |
| upstream-pr | `skills/upstream-pr/SKILL.md` | HolmesGPT Issue/PR scope, signed-off commits, review loop |

Canonical source of truth for skills is `skills/`. Cursor wrappers live in `.cursor/skills/`.

## Spec

Full design: `OpsPilot_完整开发技术文档.md` and `docs/`.
