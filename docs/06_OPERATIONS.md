# 运维

## 本地

```bash
cp .env.example .env
uv sync --extra dev
make test
docker compose up -d postgres
```

Holmes 容器（需要 Azure 凭证）：

```bash
docker compose --profile holmes up
```

## 阶段

| Phase | 内容 | 现在 |
|---|---|---|
| Init | 仓库、模型、文档、Skills | 已完成 |
| 0 | Holmes 基线、stream、approval、Azure schema | 下一步 |
| 1 | 事故模拟 S01–S04 | 未开始 |
| 2 | MCP 工具 | 契约已冻结 |
| 3 | Single-Agent 调查 | 未开始 |
| 4 | 安全修复控制面 | 策略骨架已有 |
| 5+ | Benchmark / Verifier / SFT | 门禁见 `AGENTS.md` |

升级 Holmes 版本必须先跑兼容性测试，再改 `config/holmesgpt.pin`。
