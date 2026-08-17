# Live 查空了：问题与修复

记录时间：2026-08-17  
前置：`docs/09_LIVE_AZURE_INVESTIGATION_FIX.md`（null 可选参数 + 预算重复计数）已修好。  
范围：Phase 2 可观测查询语义 + Phase 3 Prompt + live 装配等待。不重做 Phase 0–6，不改 Verifier 编排，不开始 UI / Multi-Agent / SFT。  
不把 ground truth / verification code 写进 prompt 或 tool 结果。

复跑对照（修复 09 之后、本层之前）：

- Single-Agent：`artifacts/benchmarks-live/b5c72618-d7f7-4870-bc7d-31b16e7a84d0/report.md`（综合分 0.517，根因 0.000，4/4 `diagnosis_complete`）
- Verifier：`artifacts/benchmarks-live-verify/b158a1e0-b8d2-48dc-baa3-ff8b153d538e/report.md`（综合分 0.487，根因 0.000；4/4 都审到）

## 结论

控制面已经不再挡调查。根因仍为 0，是因为工具返回了「成功但为空」的证据，模型据此写成「没有错误」。空结果被当成健康信号。

## 现象（S01 live 轨迹）

调查时刻约 `14:30:58Z`。Agent 查询：

| 调用 | 参数 | 结果 |
|---|---|---|
| `query_service_metrics` | checkout `error_rate`，`path=/checkout`，`14:20:00Z`–`14:30:00Z` | `points: []`，`aggregated_value: null` |
| `query_service_logs` | checkout `severity=error`，同一窗口 | `returned: 0` |
| `get_recent_deployments` | checkout，`08:30:00Z`–`14:30:00Z` | `returned: 0` |

诊断：「各服务都没有错误证据」。Verifier 拒绝这类结论，没有推出正确根因。

Lab 里 checkout 的 HTTP path 标签是 `/orders`，不是 `/checkout`。Prometheus scrape 间隔 5s。故障订单发生在 `14:30:00` 之后时，取整到整分的 `end` 会把当前故障切掉。

## 根因

1. **猜 path 把序列滤空**  
   `http_requests_total` 带 `path` 标签。Agent 传 `path=/checkout`，PromQL 加上 `path="/checkout"`，没有匹配序列。工具返回空点且 `ok: true`，没有说明该重试。

2. **`end` 取整丢掉当前分钟**  
   Prompt 说「最近约 10 分钟」，模型写成 `14:20:00Z`–`14:30:00Z`。live 装配在 `14:30:40` 左右 inject + 下单。查询窗口在故障发生前结束。部署列表也按同一 `end` 过滤，于是 `returned: 0`。

3. **`aggregation=rate` 被当成计数器**  
   `error_rate` 的 PromQL 已经是 `rate()` 比值。工具又用 `(last - first) / duration` 再算一次，短窗口上得到接近 0 或略负的数。模型把「错误率 ≈ 0」当成没有故障。

4. **Loki 只搜 `service_name` + 行内 `error`**  
   stdout JSON 有 `"level":"error"`，OTLP 导出的 body 往往只有消息文本，不含单词 `error`。只跑 `{service_name="checkout"} |~ "(?i)error"` 会得到 0 行。Harness 自己也会试 `{service="checkout"}`。

5. **live 只睡 2 秒**  
   Prometheus 5s 刮一次，OTLP 批量导出也要几秒。3 个订单之后立刻调查，指标和日志可能还没进后端。

6. **空结果没有 `suggested_fix`**  
   `ok: true` + 空点被模型读成「查过了，没问题」。

## 修复

| 层 | 改动 |
|---|---|
| 时间窗 | `parse_time_range`：若 `end` 早于现在且不超过 120 秒，把 `end` 收到现在，并标 `end_extended`。历史窗口不动。所有只读工具共用。 |
| Metrics | 带 `path` 且 0 点时，去掉 path 再查一次；返回 `path_ignored` / `path_requested`。`aggregation=rate` 改为对已有点取均值，并返回 `peak_value`。空序列带 `empty` + `suggested_fix`。 |
| Logs | 依次尝试 `service_name` / `service`，以及行内 `error`、`json.level`、`detected_level`。空结果带 `suggested_fix`。 |
| Prompt | 仍用冻结 ID `phase3-single-agent-v1`（不重切 offline baseline）：`end` 用当前 UTC；不要猜 path；不要把空点当成健康；先看 `suggested_fix`。不写场景答案，不列会泄题的故障名。 |
| Catalog | 仍用冻结 ID `phase2-readonly-v1`。输出增加 `empty` / `suggested_fix` / `path_ignored`，不改离线轨迹。 |
| Live 装配 | inject + 3 单之后，等到 checkout 近 1 分钟有 `http_requests_total` 增量，并等到 Loki 有该服务日志（不使用 verification token）。 |

## 复跑（空证据修复之后）

Single-Agent：`artifacts/benchmarks-live/d89121a4-4f24-4e50-bcdf-fe02886f5e81/report.md`

- 4/4 `diagnosis_complete`，综合分 0.523，根因仍 0.000（自然语言对不上 scorer 的 slug），unsafe 0。
- 工具能读到真实日志/指标，不再写成「没有错误」。S01 已接近「DB 连接等待超时」；S02–S04 仍容易收成同一套 DB 叙事。

Verifier 第一次复跑在 S01 Investigator 完成后崩溃：`assert_agent_text_is_safe` 扫了整份 bundle，诊断里的 “connection pool” 触发了作者侧禁词。这是工具查到的措辞，不是 prompt 泄题。已改为只检查模板（`src/opspilot/verifier/prompt.py`），follow-up 同样不把证据摘要当泄题。

Verifier 修好后再跑：`artifacts/benchmarks-live-verify/d83f0a51-f229-4715-a561-189fcea39bd3/report.md`（综合分 0.517，根因 0.000，4/4 审完，unsafe 0）。S01/S03/S04 有 follow-up；S02 直接 accept。

## 不在本次范围

- 不把 `db_pool_*` 等答案写进 prompt（工具 schema 里已有 metric 枚举）。
- 不把 ground-truth slug 写进 prompt 来抬根因分。
- 不晋升 Verifier，不加 Multi-Agent。

空证据修好后根因仍为 0 的打分层，见 `docs/11_DIAGNOSIS_SCORING.md`。连跑残留见 `docs/12_LIVE_CROSS_SCENARIO_RESIDUE.md`。reset 后静默再 inject 见 `docs/13_LIVE_QUIET_BEFORE_INJECT.md`。

## 如何复验

```powershell
python -m uv run pytest tests/unit tests/contract tests/security -q
```

重建 MCP 后再跑 live：

```powershell
docker compose --profile holmes up -d --build opspilot-observability opspilot-deployments opspilot-runbooks opspilot-remediation
docker compose --profile holmes up -d --force-recreate holmes
python -m uv run python -m benchmarks.cli --live --out artifacts/benchmarks-live
```

不要打印 `.env` 里的 endpoint / API key。

## 预期

- `path=/checkout` 不应再得到「成功且完全无点」然后结案；应回退到服务级序列并说明 path 被忽略。
- `end` 取整到当前分钟之前几十秒时，窗口应延伸到现在。
- `error_rate` + `aggregation=rate` 不应再把 0.12/0.18 收成接近 0。
- 空结果必须带 `empty: true` 和 `suggested_fix`。
- Prompt / tool 结果仍不含 ground truth。
