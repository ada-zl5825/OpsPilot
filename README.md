# OpsPilot Incident Lab

基于 [HolmesGPT](https://github.com/HolmesGPT/holmesgpt) 的可审计多工具事故响应、受控修复与 Agent 轨迹评测平台。

OpsPilot does not reimplement the HolmesGPT agent loop. This repo owns the incident simulator, MCP tools, policy/approval control plane, and trajectory benchmark.

## Current status

**Phase 0–4 complete.** HolmesGPT is pinned to `robustadev/holmes:0.39.0`. S01–S04 lab, Phase 2 read-only MCP, Single-Agent investigation, and the safe remediation control plane are in place. Next: Phase 5 Benchmark v1. New window: start from [`docs/HANDOFF.md`](docs/HANDOFF.md).

```bash
make holmes-up
make holmes-smoke
```

## Quick start

```bash
cp .env.example .env
uv sync --extra dev
make test
docker compose --profile lab up -d --build
python -m uv run python -m simulator.harness --cycles 2
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
