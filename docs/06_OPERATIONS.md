# 运维

## 本地

```bash
cp .env.example .env
python -m uv sync --extra dev
make test
docker compose up -d postgres
```

## Phase 1 lab

```bash
docker compose --profile lab up -d --build
python -m uv run python -m benchmarks.datasets.check_integrity
python -m uv run python -m simulator.harness --cycles 2
```

Storefront: `http://localhost:8080/api/orders`  
Controller: `http://localhost:8090/v1/scenarios`  
Prometheus / Loki / Tempo: `9090` / `3100` / `3200`

The harness does not call an LLM. It checks dataset integrity, two inject/reset cycles, and live recovery.

```bash
docker compose --profile lab down
```

## Phase 0 Holmes

```bash
make holmes-up
make holmes-smoke
```

Holmes HTTP: `http://localhost:5050/healthz`  
Lab MCP: `http://localhost:8000/mcp`  
Observability / Deployment / Runbook / Remediation MCP: `8001` / `8002` / `8003` / `8004`

Phase 2 工具测试（不接 LLM，不需要 lab）：

```bash
python -m uv run pytest tests/unit tests/contract tests/security -q
```

## Phase 3 Single-Agent

不接 LLM 的检查：

```bash
python -m uv run python -m opspilot.cli investigate --all --prompt-only
python -m uv run pytest tests/unit/test_investigation_runner.py tests/contract/test_investigation_prompt_integrity.py -q
```

Live Azure（需 lab + holmes profile，先 inject 场景）：

```bash
docker compose --profile lab --profile holmes up -d --build
# Invoke-WebRequest http://localhost:8090/v1/scenarios/S01/inject -Method POST
python -m uv run python -m opspilot.cli investigate --scenario S01
python -m uv run python -m opspilot.cli replay --run-id <run_id>
```

轨迹目录：`artifacts/investigations/{run_id}/`。Ground truth 不会进入 prompt。写工具会被拒绝，失败 run 不会标成 `diagnosis_complete` / `resolved`。

## Phase 4 安全修复控制面

不接 LLM 的检查：

```bash
python -m uv run pytest tests/unit/test_remediation_service.py tests/security/test_remediation_gates.py tests/contract/test_phase4_tool_contracts.py -q
```

API（control plane，不给 Agent）：

```text
POST /api/incidents/{run_id}/proposals
POST /api/proposals/{id}/dry-run
POST /api/proposals/{id}/approve   # body: actor_id, actor_role, proposal_digest
POST /api/proposals/{id}/reject
POST /api/proposals/{id}/execute   # 人类 + digest；Agent 目录里没有这个工具
POST /api/proposals/{id}/rollback
POST /api/proposals/{id}/verify
```

Holmes 只加载 propose / dry-run / verify。`execute_approved_proposal` 与 `rollback_execution` 不注册到 Remediation MCP。

## Phase 5 Benchmark v1

不接 LLM 的离线评测与回归门禁：

```powershell
python -m uv run python -m benchmarks.datasets.check_integrity
python -m uv run python -m benchmarks.cli --offline --gate
python -m uv run pytest tests/benchmark -q
```

Holdout：`--split holdout`（不用于调 Prompt）。Live Azure 仅手动：`python -m benchmarks.cli --live` 或 `.github/workflows/benchmark-live.yml`。

## Phase 6 Verifier

不接 LLM 的检查：

```powershell
python -m uv run python -m opspilot.cli verify --all --prompt-only
python -m uv run python -m experiments.single_vs_verifier --offline
python -m uv run pytest tests/unit/test_verifier_runner.py tests/contract/test_verifier_prompt_integrity.py tests/benchmark/test_verifier_ab.py -q
```

Investigator 与 Verifier 共用总 Tool Budget，最多一次补查，交接只用 Pydantic Schema。不要把这理解成 Multi-Agent 编排。Holdout 不用于调 Verifier Prompt。

Live `/api/chat` 需要 `.env` 中的 Azure 凭证。没有凭证时，容器健康检查仍应通过。Phase 0 已在有凭证的本机验收通过；复验步骤见 `docs/HANDOFF.md`。

```bash
make holmes-down
```

## 阶段

| Phase | 内容 | 现在 |
|---|---|---|
| Init | 仓库、模型、文档、Skills | 已完成 |
| 0 | Holmes 基线、stream、approval、Azure schema | 已完成（含 live Azure / MCP / approval） |
| 1 | 事故模拟 S01–S04 | 已完成（不接 LLM） |
| 2 | MCP 工具 | 已完成（Observability / Deployment / Runbook，只读） |
| 3 | Single-Agent 调查 | 已完成（单元/契约测试覆盖 S01–S04；live Azure 手动） |
| 4 | 安全修复控制面 | 已完成（Proposal → Policy → Dry Run → Approval → Executor） |
| 5 | Benchmark v1 | 已完成（离线 Deterministic / Single-Agent、scorer、regression gate） |
| 6 | Verifier 实验 | 已完成（离线 A/B：不晋升；Simple Agent 仍是默认） |
| 7+ | SFT / UI | 不要开始 UI / Multi-Agent 编排 / SFT |

升级 Holmes 版本必须先跑兼容性测试，再改 `config/holmesgpt.pin`。
