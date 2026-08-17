# Live 连跑残留：问题、过程与改法

记录时间：2026-08-17  
范围：lab 本场 onset、只读 MCP 时间窗裁剪、live 调查窗。不重做 Phase 0–6，不改 Holmes pin，不把四个故障名写进 prompt，不开始 UI / Multi-Agent / SFT。  
前置：`docs/10_LIVE_EMPTY_EVIDENCE_FIX.md`（工具能读到真实日志）、`docs/11_DIAGNOSIS_SCORING.md`（slug 假 0 已拆开）。

## 1. 问题

空证据修好后，最新 live `d89121a4` 四条都是 `diagnosis_complete`、unsafe 0。新 rubric 打分：S01=0.9，S02=0，S03=0.8，S04=0。

S02–S04 仍收成同一套「database connection wait」，不是 scorer 误杀。对照轨迹：

| 场 | 本场应看到的信号 | Agent 实际查到的 | 诊断 |
|---|---|---|---|
| S01 | checkout error：connection wait | 50 条 error 日志，`error_rate≈0.11` | 机制对 |
| S02 | warning：cache lookup latency；HTTP 200 | checkout **error** 23 条 + `error_rate≈0.10` | 写成 DB wait |
| S03 | 1.4.2 + order total failed | 两者都有，外加 DB wait | 发布点到了，主因被污染 |
| S04 | payment span / downstream deadline | checkout error **47** 条；没打 trace | DB + order total + 笼统 timeout |

S02 的 cache 行是 **warning**（`checkout/main.py`），`severity=error` 本来就看不到。更关键的是：live 按 S01→S04 连跑，每场调查窗约 10 分钟，而场间隔只有几十秒。`reset_all` 只关 fault flag，**不清 Loki / Prometheus 计数**。S01 的 5xx 和 `database connection wait` 还在窗里，后面三场一搜 error 就先看到它。

这是 Waterloo RF-03：把最先看到的症状观察者当成根因。S01 那句话碰巧是对的，于是成了吸引子。

打开的 `dcf55e49` 是更早一轮（null 参数 + 空日志），不要拿它当本层对照。

## 2. 过程

1. 用新 `diagnosis_rubric` 重打 `d89121a4` 四条原文，确认假 0 / 真塌缩已经分开。
2. 对照四场 `events.jsonl` / `evidence.json`：S02 从未查 cache 指标；S04 从未打 `get_trace_summary`；S02/S04 的 error 条数远超本场 3 单。
3. 读 `benchmarks/live.py`：`_arm_lab` 是 `reset_all` → inject → 3 单 → 等 Prom/Loki，但查询 start 仍由模型写成 now−10min。
4. 读 checkout：S02 日志是 warning；S01 error 在 `TimeoutError` 分支。单场 lab 是对的，坏在连跑残留 + 只搜 error。
5. 改法选「本场 onset 硬裁窗」，不 rebuild，不把 slug 写进 prompt。

## 3. 方法（两层，互为备份）

**A. 控制面记下本场开始（硬保证）**

- inject 写入 `lab:active_scenario` + `lab:injected_at`。
- `GET /v1/active` 返回 `{active, scenario_id, injected_at}`，不含 ground truth / verification code。
- reset / reset_all 清掉 active。
- 只读 MCP 的 `window_or_error`：若设置了 `LAB_CONTROLLER_URL`，把 `start` 抬到 `injected_at − 30s`（刮取余量）。模型仍传 10 分钟，也带不走上场 Loki/Prom。
- 裁剪后工具结果带 `start_clipped: true`。
- Controller 不可达则不裁（holmes-only / 单测 fail-open）。

**B. Live prompt 带同一窗口（软引导）**

- `AgentVisibleIncident.investigation_window` 可选。离线不设，prompt 文本与 v1 基线一致。
- Live `_arm_lab` 用 inject 的 `injected_at` 生成 start/end，交给 Investigator / Verifier。
- 有窗口时才追加：不要把 start 提前；窗前的行是另一场；`severity=error` 可能漏掉 warning/info；多服务同时出错先看 trace；`rejected_hypotheses` 至少否决一个已核对的备选。
- 不写 `connection pool` / cache collapse / payment timeout / 四个 slug。

Prompt 仍用冻结 ID `phase3-single-agent-v1`。不重切 offline baseline。

## 4. 不在本次范围

- 不改 checkout 日志级别（S02 用 warning 是场景设计）。
- 不把 `db_pool_*` 或四个答案写进 prompt。
- 不晋升 Verifier，不加 Multi-Agent。
- 不 wipe Loki / 不重启 Prom（reset 语义保持「关 flag」）。
- 本变更不重跑 Azure-live；修完后需重建 MCP 镜像并 `--force-recreate` observability / deployments。

## 5. 如何复验

```powershell
python -m uv run pytest tests/unit tests/contract tests/security tests/benchmark -q
python -m uv run python -m benchmarks.datasets.check_integrity
python -m uv run python -m benchmarks.cli --offline --gate
```

改 MCP / controller 后：

```powershell
docker compose --profile lab --profile holmes up -d --build controller opspilot-observability opspilot-deployments
```

Live（手动，不进普通 PR）：

```powershell
python -m uv run python -m benchmarks.cli --live --out artifacts/benchmarks-live
```

期望：S02 的 error 日志不再混进 S01 的 connection wait；S02 `error_rate` 不再吃上场 5xx；S03 仍能看到本场 1.4.2；S04 窗内以本场信号为主。S02 若只搜 error 仍可能为空，应走 `severity=all` / 其它 metric，而不是抄上场 DB 叙事。

## 6. 预期分（新 rubric，不保证一次 live 全满）

| 场 | 残留修掉之后 |
|---|---|
| S01 | 仍应 ≥ 0.8（本场信号就是 wait） |
| S02 | 不再因为上场 error 行而稳 0；真分开 cache 才能上分 |
| S03 | 仍应 ≥ 0.7；不再被上场 wait 污染到 0 |
| S04 | 0 只应出现在没看 trace / 没点到 payment 时，而不是抄 DB |
