# Live Azure 调查失败：问题与修复

记录时间：2026-08-17  
范围：Phase 2 MCP 运行时 + Phase 3 调查预算。不重做 Phase 0–6，不改 Verifier 编排，不开始 UI / Multi-Agent / SFT。  
相关 live 报告：

- Single-Agent：`artifacts/benchmarks-live/5eb71070-4ad7-4aae-8650-641ca1669ddd/report.md`（综合分 0.500，根因 0.000）
- Verifier：`artifacts/benchmarks-live-verify/e6b28715-24be-4dd0-abec-78472b3698d4/report.md`（综合分 0.430，根因 0.000）

离线门禁仍然有效：Deterministic 1.000，Single-Agent 0.837，Verifier 不晋升。那份离线数据没有覆盖 Azure 真调用路径。

## 结论

不是 Azure 凭证坏了，也不是 Proposal → Policy → Approval 写隔离错了。Live 失败是三层叠加：

1. **主因（实现）**：Azure / gpt-4o 对未使用的可选参数发 JSON `null`，FastMCP 按 `str` 校验直接拒绝。
2. **预算语义过紧**：`max_repeats_per_tool` 按工具名计数，把「5 个服务各查一次 + 失败重试」当成死循环。
3. **评测覆盖不足**：离线轨迹从不发 `null`、从不跨服务扇出，所以合同测试全绿。

Verifier 在 S02–S04 被 `duplicate_tool_limit` 跳过，是既有策略，不是编排器 bug。S01 上 Verifier 拒绝站不住的结论，行为正确。

## 现象

| 场景 | Live 结果 | 轨迹里实际发生的事 |
|---|---|---|
| S01 | 给出含糊诊断（「error rate 升高，缺日志」） | `path=null` / `contains=null` / `trace_id=null` 先失败；重试后 logs `returned=0`；`error_rate` 在 30 分钟窗上约为 `-0.0005` |
| S02–S04 | `evidence_insufficient` / `duplicate_tool_limit` | 对 5 个服务并行打同一工具；失败后再用 `""` 重试；同一工具名远超 3 次 |
| Verifier S02–S04 | 未运行 | Investigator 已因重复上限停住，`_SKIP_VERIFIER` 包含 `DUPLICATE_TOOL_LIMIT` |

典型 FastMCP 错误（S01 / S02 `events.jsonl`）：

```text
validation error for query_service_metricsArguments
path  Input should be a valid string  input_value=None

validation error for query_service_logsArguments
contains  Input should be a valid string  input_value=None

validation error for get_trace_summaryArguments
trace_id  Input should be a valid string  input_value=None
```

同一查询在第二次改成 `path=""` / `contains=""` 后成功。这不是后端挂了，是参数校验拒 `null`。

## 根因

### 1. Azure schema 门禁和调用时行为不是同一件事

合同测试要求 JSON Schema **不能**出现 `anyOf` / `null`（Azure 不吃）。因此 FastMCP 签名写成：

```python
path: str = ""
contains: str = ""
trace_id: str = ""
```

广告出去的 schema 是 `type: string`，测试通过。  
gpt-4o 对「我没用的可选字段」仍会传 `null`。Pydantic 把 `None` 当成类型错误，工具在进业务逻辑之前就失败。

`azure_input_schema` / `validate_tool_schema_for_azure` 只检查 schema 文本，不检查「调用参数带 null」。

### 2. 预算按工具名计重复

默认 `max_repeats_per_tool=3`，计数对象是所有 `TOOL_CALL`，不论成败、不论服务。

一次合理的「5 服务 latency」就会到 5。再加上 null 失败重试，S02 一轮出现 25 次工具调用。预算又在 Holmes 整轮 `ask()` **之后**才评估，拦不住单轮扇出。

`max_repeats_per_query` 本意是「同一 tool+params 不要刷」，但失败结果也进了 fingerprint 计数。

### 3. 调查窗口与刚 reset 的 lab

Prompt 原先建议「最近 30 分钟」。Live 流程是 `reset_all` → inject → 3 个订单 → 睡 2 秒 → 立刻调查。Prometheus counter 刚归零，`rate()` 在长窗口上接近 0 甚至略负。模型只查了 `error_rate` / `latency_p95`，把空日志和近零错误率当成「短暂抖动」。

## 修复

### A. 运行时丢掉 JSON null（不改 Azure schema）

- `mcp_servers/common/null_args.py`：`drop_null_arguments` 删除值为 `None` 的键，让可选字段走默认值。
- `StrictModel` 在 `model_validator(mode="before")` 里丢掉 null；`parse_model` 同样处理。
- `create_mcp()` / `run_streamable_http()` 在 FastMCP `call_tool` 前安装同一层剥离，覆盖 Holmes → MCP 真路径。
- Schema 仍禁止 `anyOf`/`null`。不把字段改成 `str | None`。

合同测试：`tests/contract/test_azure_null_optional_args.py`  
覆盖 `path=null`、`contains=null`、`trace_id=null`、`workflow=null`，并断言生成 schema 仍然 Azure-safe。

### B. 重复预算改为「成功的 query fingerprint」

`evaluate_budget` 现在：

- `max_tool_calls`：仍计每一次 `TOOL_CALL`（含失败），防止只失败不成功的死循环。
- `max_repeats_per_query` / `max_repeats_per_tool`：只计 **成功** 的 `TOOL_RESULT`，且按 query fingerprint（工具名 + 参数）。
- 同一工具、不同服务或不同 metric，不再算重复。

Prompt 同步：不要发 JSON null；刚发生的故障优先用约 10 分钟短窗；允许跨服务使用同一工具。

Verifier skip 规则未改。先让 Investigator 能跑完，再谈晋升。

## 不在本次范围

- 不重做 Verifier / 不加 Multi-Agent 对话。
- 不把 ground truth 或 metric「标准答案」写进 prompt。
- 不改 Holmes 镜像 pin。
- 未在本变更里重跑 Azure-live（需要重建 MCP 容器后再跑）。

## 如何复验

```powershell
python -m uv run pytest tests/unit tests/contract tests/security -q
```

改动已进镜像构建上下文时，重建 Phase 2/4 MCP 后再跑 live：

```powershell
docker compose --profile lab --profile holmes up -d --build opspilot-observability opspilot-deployments opspilot-runbooks opspilot-remediation
python -m uv run python -m benchmarks.cli --live --out artifacts/benchmarks-live
```

不要打印 `.env` 里的 endpoint / API key。

## 预期（修完后、重跑 live 前）

- 可选参数带 `null` 不应再出现 `Input should be a valid string`。
- 5 个服务各查一次 metrics 不应单独触发 `duplicate_tool_limit`。
- 同一成功 query 连续超过 `max_repeats_per_query` 仍应停下。
- 写路径与 Agent 不可见 execute/rollback 的约束不变。

## 复跑记录（2026-08-17）

重建时 `.dockerignore` 排除了整个 `src`，`COPY src/opspilot` 失败。已去掉该行后 `--build` 成功，并 `--force-recreate holmes`。

| 条件 | 报告 | Composite | Root cause | 四条是否跑完诊断 | `duplicate_tool_limit` | Verifier 是否审到 |
|---|---|---:|---:|---|---|---|
| 修复前 Single-Agent | `artifacts/benchmarks-live/5eb71070-...` | 0.500 | 0.000 | 仅 S01 | S02–S04 | — |
| 修复后 Single-Agent | `artifacts/benchmarks-live/b5c72618-d7f7-4870-bc7d-31b16e7a84d0` | 0.517 | 0.000 | 4/4 `diagnosis_complete` | 无 | — |
| 修复前 Verifier | `artifacts/benchmarks-live-verify/e6b28715-...` | 0.430 | 0.000 | — | S02–S04 被 skip | 仅 S01 |
| 修复后 Verifier | `artifacts/benchmarks-live-verify/b158a1e0-b8d2-48dc-baa3-ff8b153d538e` | 0.487 | 0.000 | Investigator 4/4 完成 | 无 | 4/4 都审了；S01–S03 `reject`，S04 `accept` 后诊断无效 |

轨迹里不再出现 `Input should be a valid string`。`unsafe=0`，hard fail=0。

根因仍为 0：Agent 查到的 `error_rate` / error logs 经常是空点或 `returned=0`（例如 S01 对 checkout 带了 `path=/checkout`，Prometheus 无匹配序列），于是写成「没有错误证据」。下一层修复见 `docs/10_LIVE_EMPTY_EVIDENCE_FIX.md`。
