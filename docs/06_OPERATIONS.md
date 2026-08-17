# 运维

## 本地

```bash
cp .env.example .env
python -m uv sync --extra dev
make test
docker compose up -d postgres
```

## Phase 0 Holmes

```bash
make holmes-up
make holmes-smoke
```

Holmes HTTP: `http://localhost:5050/healthz`  
Lab MCP: `http://localhost:8000/mcp`

Live `/api/chat` 需要 `.env` 中的 Azure 凭证。没有凭证时，容器健康检查仍应通过。Phase 0 已在有凭证的本机验收通过；复验步骤见 `docs/HANDOFF.md`。

```bash
make holmes-down
```

## 阶段

| Phase | 内容 | 现在 |
|---|---|---|
| Init | 仓库、模型、文档、Skills | 已完成 |
| 0 | Holmes 基线、stream、approval、Azure schema | 已完成（含 live Azure / MCP / approval） |
| 1 | 事故模拟 S01–S04 | 下一步 |
| 2 | MCP 工具 | 契约已冻结 |
| 3 | Single-Agent 调查 | 未开始 |
| 4 | 安全修复控制面 | 策略骨架已有 |
| 5+ | Benchmark / Verifier / SFT | 门禁见 `AGENTS.md` |

升级 Holmes 版本必须先跑兼容性测试，再改 `config/holmesgpt.pin`。
