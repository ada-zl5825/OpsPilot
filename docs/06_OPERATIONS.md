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
Observability / Deployment / Runbook MCP: `8001` / `8002` / `8003`

Phase 2 工具测试（不接 LLM，不需要 lab）：

```bash
python -m uv run pytest tests/unit tests/contract -q
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
| 4 | 安全修复控制面 | 策略骨架已有 |
| 5+ | Benchmark / Verifier / SFT | 门禁见 `AGENTS.md` |

升级 Holmes 版本必须先跑兼容性测试，再改 `config/holmesgpt.pin`。
