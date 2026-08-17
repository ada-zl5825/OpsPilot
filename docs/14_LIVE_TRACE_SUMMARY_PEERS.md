# Live S04：trace 摘要看不见下一跳

记录时间：2026-08-17  
范围：`get_trace_summary` 补 peer services、真实 error_count、最慢 span。不重做 Phase 0–6，不改 Holmes pin，不把 `payment` 写进 prompt，不开始 UI / Multi-Agent / SFT。  
前置：`docs/13_LIVE_QUIET_BEFORE_INJECT.md`（连跑残留已清）。对照 live：`artifacts/benchmarks-live/32631ef9-b9bb-45d3-bdda-2e13d003b038`，调查 `5bfda48c-79c4-4988-8bb4-f4a44f85ac4c`。

## 1. 问题

静默等待之后 S01–S03 根因已分开（0.9 / 1.0 / 1.0）。S04 从 0 抬到 0.5：机制写对了（`downstream request deadline exceeded`），人写成了 gateway。

S04 当场不是残留：

| 信号 | 值 | 含义 |
|---|---|---|
| gateway / checkout `error_rate` | 都是 0.488 | 反代镜像，不是两个独立故障 |
| gateway / checkout `latency_p95` | 都是 4.85s | 同上 |
| gateway 日志 error / all | 0 条 | gateway 自己没超时，只是转发了 checkout 的 504 |
| checkout error | 10 条，`target: payment` | 本场信号已在日志里 |
| `get_trace_summary(gateway/checkout)` | `error_traces: 0`，`services` 只有被查的那个服务 | 工具把下一跳藏起来了 |
| `service=payment` | 从未调用 | 停在第一跳 |

题面 “edge API and checkout” 是 S04 设计好的边沿吸引子。模型从 gateway 起手没错；错在工具返回的 trace 摘要无法比较下一跳，于是把镜像 5xx 当成 gateway 高延迟。

根因在 `LiveTracesBackend.search`：Tempo `/api/search` 只有 root 服务和时长，代码却写死 `error_count: 0`、`services: [查询的 service]`。`/api/traces/{id}` 其实有 resource 和 span，`_by_id` 也没数 ERROR，也没读 `peer.service`。

Prompt 已经说 “多服务先看 trace”。看了也没用。

## 2. 过程

1. 对照 `5bfda48c` 的 12 次工具调用：只围着 gateway + checkout。
2. 读 `simulator/services/gateway/main.py`：8s 内收到 checkout 504 就原样转发，不打 error。
3. 读 checkout：`downstream request deadline exceeded` + `target: payment`。
4. 读 `mcp_servers/observability/backends.py`：search 写死零错误；`_by_id` 丢掉 peer。
5. 改法选补 trace 摘要，不把 payment 写进 prompt，不切 `phase3-single-agent-v1`。

## 3. 方法

对 Tempo search 命中的**最长 5 条**再拉 `/api/traces/{id}`，用 OTLP 批次汇总：

- `services`：resource `service.name` + span `peer.service`
- `peer_services`：services 去掉 root
- `error_count`：span `status.code` 为 ERROR（2 / `STATUS_CODE_ERROR`）
- `slowest_span`：`{name, service, duration_ms, peer_service}`
- 未 enrich 的行不再伪造 `error_count: 0`
- 顶层 `summary` 带 `services` / `peer_services` / `slowest_span` / 真实 `error_traces`
- 若有 peer：`suggested_fix` 提示去查这些服务（不点名 payment）

单条 `trace_id` 查询走同一套汇总。某一条 enrich 失败则 fail-open，保留 search 行。

不写四个 slug。Prompt ID 仍是 `phase3-single-agent-v1`。不重切 offline baseline。

## 4. 不在本次范围

- 不把 `payment` / “connection pool” 写进 prompt。
- 不改 S04 用户报告（边沿吸引子是场景设计）。
- 不晋升 Verifier，不加 Multi-Agent。
- 若工具已露出 peer，模型仍把 gateway 当根因，再谈诊断协议，不是再改 Tempo。

## 5. 如何复验

```powershell
python -m uv run pytest tests/unit tests/contract tests/security tests/benchmark -q
python -m uv run python -m benchmarks.cli --offline --gate
```

改了 MCP 镜像后：

```powershell
docker compose --profile lab --profile holmes up -d --build --force-recreate opspilot-observability
```

Live（手动，不进普通 PR）：

```powershell
python -m uv run python -m benchmarks.cli --live --scenario S04 --out artifacts/benchmarks-live
```

期望：`get_trace_summary(service=checkout)` 的 `summary.peer_services` 含 payment，或 `slowest_span.peer_service` 为 payment；S04 localization 不再因为 “没看见下一跳” 而稳 0。不保证一次 live 满 1.0。
