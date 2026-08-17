# Live 连跑：reset 后先静默再 inject

记录时间：2026-08-17  
范围：live harness 在 `reset_all` 之后等到上场 5xx / error 日志滚出窗口，再 inject；MCP 裁窗余量从 30s 收到 5s。不重做 Phase 0–6，不改 Holmes pin，不把四个故障名写进 prompt，不开始 UI / Multi-Agent / SFT。  
前置：`docs/12_LIVE_CROSS_SCENARIO_RESIDUE.md`（本场 onset 裁窗已落地）。对照 live：`artifacts/benchmarks-live/df7f428c-b7da-475d-9b54-0d6ea59b36ad`。

## 1. 问题

`df7f428c` 重建 MCP 后重跑：裁窗是生效的。S02 查询 start 从 `15:25:33` 被抬到 `15:25:41`（`injected_at − 30s`）。控制面仍绿（unsafe 0，hard fail 0）。S01 root cause 1.0，S03 0.8。S02 / S04 仍为 0。

S02 当场证据：

| 信号 | 值 | 本场该有的 |
|---|---|---|
| `severity=error` | 14 条 | 0（S02 是 warning + HTTP 200） |
| `error_rate` | ≈ 0.35 | 接近 0 |
| traces `error_traces` | 0 | 0（对） |
| 诊断 | database connection wait | cache / Redis latency |

不是 scorer 误杀，也不是裁窗没挂上。连跑间隔只有几十秒，两件事叠在一起：

1. **`injected_at − 30s` 太宽。** 上场调查刚 `reset`，这 30 秒正好覆盖 S01 最后的 `database connection wait` error 行。
2. **Prometheus `rate()` / `increase()` 不清零。** `reset_all` 只关 fault flag。S01 的 5xx 计数还在 1 分钟窗里，所以 S02 仍看到 `error_rate ≈ 0.35`。模型先搜 error，再写成同一套 DB 叙事。

S04 不再主写 DB，但收成 order total / downstream deadline，仍是上场吸引子，不是 payment span。

打开的 `dcf55e49` 仍是更早的 null-arg / 空日志轮次，不要拿它当本层对照。

## 2. 过程

1. 读 S02 `events.jsonl` / `evidence.json`：确认 `start_clipped` 对应的时间已被抬高，但 error 条数和 error_rate 仍是上场量级。
2. 对照 checkout：S02 只打 warning `cache lookup exceeded latency budget`；14 条 error 不可能是本场。
3. 算时间线：S01 调查期间 fault 仍开着，traffic 持续打 5xx → reset → 立刻 inject S02。`increase(...[1m])` 至少还要约 60s 才滚干净。
4. 改法选「reset 后等到上场窗口静默，再 inject」+ 把裁窗余量收到 5s。不 wipe Loki，不重启 Prom，不改 S02 日志级别，不把 slug 写进 prompt。

## 3. 方法

**A. Live harness：静默后再武装（主修复，跑在宿主机，不必为这一条 rebuild）**

- `_arm_lab`：`reset_all` → 等到 `prior_incident_quiet` → `inject` → 3 单 → 等本场 Prom/Loki。
- 静默条件（同时成立）：
  - `sum(increase(http_requests_total{service="checkout",status=~"5.."}[1m])) ≤ 0.5`
  - 近 20s Loki 没有 `{service_name="checkout"} |~ "(?i)error"` 命中
- 超时 120s 则失败，不带着上场 5xx 进入下一场。
- 第一场 S01 本来就没有上场 5xx，会立刻通过。

**B. 裁窗余量 30s → 5s（纵深，MCP 镜像要重建）**

- `ACTIVE_CLIP_SLACK_SECONDS = 5`（`mcp_servers/common/time_range.py`）
- `WINDOW_SLACK_SECONDS = 5`（`src/opspilot/investigation/window.py`）
- 调查窗不再为了凑满 60s 把 start 往 inject 之前拉；不够长就向后垫 `end`。
- 模型仍可传 10 分钟；MCP 把 start 抬到 `injected_at − 5s`。

不写 `connection pool` / cache collapse / payment timeout / 四个 slug。Prompt ID 仍是 `phase3-single-agent-v1`。不重切 offline baseline。

## 4. 不在本次范围

- 不改 checkout 日志级别（S02 用 warning 是场景设计）。
- 不把 `db_pool_*` 或四个答案写进 prompt。
- 不晋升 Verifier，不加 Multi-Agent。
- 不 wipe Loki / 不重启 Prom（reset 语义保持「关 flag」）。
- 静默等待之后若 S02 仍写 DB、S04 仍不看 payment span，才是诊断协议问题，不是再裁窗。

## 5. 如何复验

```powershell
python -m uv run pytest tests/unit tests/contract tests/security tests/benchmark -q
python -m uv run python -m benchmarks.datasets.check_integrity
python -m uv run python -m benchmarks.cli --offline --gate
```

5s 裁窗进了 MCP 镜像，改完后：

```powershell
docker compose --profile lab --profile holmes up -d --build --force-recreate opspilot-observability opspilot-deployments
```

Live（手动，不进普通 PR）：

```powershell
python -m uv run python -m benchmarks.cli --live --out artifacts/benchmarks-live
```

期望：S02 裁剪后的窗里不应再有十几条 S01 error，`error_rate` 不应再是上场 0.3+。S01 / S03 保持。S04 不应再被 DB / order-total 带跑；若仍为 0，应是没看 payment span。

## 6. 预期分（新 rubric，不保证一次 live 全满）

| 场 | 静默 + 5s 裁窗之后 |
|---|---|
| S01 | 仍应 ≥ 0.8（本场信号就是 wait） |
| S02 | 不再因为上场 error 行而稳 0；真分开 cache 才能上分 |
| S03 | 仍应 ≥ 0.7；窗内不应再混进上场 wait |
| S04 | 0 只应出现在没看 trace / 没点到 payment 时 |
