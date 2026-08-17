# OpsPilot Incident Lab

基于 [HolmesGPT](https://github.com/HolmesGPT/holmesgpt) 的可审计多工具事故响应、受控修复与 Agent 轨迹评测平台。

OpsPilot does not reimplement the HolmesGPT agent loop. This repo owns the incident simulator, MCP tools, policy/approval control plane, and trajectory benchmark.

## Current status

**Initialized.** Domain models, API skeleton, MCP catalog contract, docs, and Cursor skills are in place. Next: **Phase 0** — pin HolmesGPT `0.39.0`, parse stream events, prove approval + Azure schema compatibility.

HolmesGPT pin: `robustadev/holmes:0.39.0` (see `config/holmesgpt.pin`). Never use `:latest`.

## Quick start

```bash
cp .env.example .env
uv sync --extra dev
make test
docker compose up -d postgres
```

```bash
uv run uvicorn opspilot.api.app:app --reload
# GET http://127.0.0.1:8000/health
```

## Layout

```text
src/opspilot/     Control plane (FastAPI, domain, policy, holmes client)
mcp_servers/      Observability / Deployment / Runbook / Remediation MCP
simulator/        Fault-injection microservices (Phase 1)
benchmarks/       Trajectory eval harness (Phase 5)
skills/           Project agent skills
docs/             Architecture and operations
```

## Agent rules and skills

- `AGENTS.md` — twelve hard constraints
- `skills/holmes-upstream` — Holmes pin, stream, DCO
- `skills/mcp-toolset` — MCP schema and contracts
- `skills/incident-scenario` — scenarios and anti-cheat
- `skills/agent-eval` — harness and gates
- `skills/remediation-safety` — proposal / approval / execute
- `skills/upstream-pr` — small upstream PRs

Full spec: [`OpsPilot_完整开发技术文档.md`](OpsPilot_完整开发技术文档.md).
