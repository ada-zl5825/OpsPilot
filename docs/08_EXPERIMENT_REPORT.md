# 实验报告（Benchmark v1 + Phase 6 Verifier，离线）

冻结时间：2026-08-17  
Benchmark：`v1`  
Investigator Prompt：`phase3-single-agent-v1`  
Verifier Prompt：`phase6-verifier-v1`  
Tool catalog：`phase2-readonly-v1`  
Split：eval（16 变体）。Holdout（4 变体）独立，未用于调 Prompt。

## 条件

| 条件 | 模型 | N | 说明 |
|---|---|---|---|
| Deterministic | `deterministic-runbook-v1` | 16 | 固定 runbook；控制面批准后执行并做恢复验证 |
| Single-Agent | `single-agent-offline-v1` | 16 | 冻结调查轨迹；不接 Azure；不执行写 |
| Verifier | `single-agent-plus-verifier-offline-v1` | 16 | 同一调查轨迹 + schema-only Verifier accept；共用工具预算 |

Live Azure Single-Agent 不在本报告内，见 `benchmark-live.yml`（`workflow_dispatch`）。2026-08-17 本机 live 失败原因与修复见 `docs/09_LIVE_AZURE_INVESTIGATION_FIX.md`。

## Eval 结果（Phase 5）

| 条件 | Composite | Root cause | Evidence | Tool eff. | Recovery | Fail rec. | Escalation | Unsafe | Hard fails |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| deterministic | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| single_agent | 0.837 | 1.000 | 1.000 | 0.914 | 0.000 | 1.000 | 1.000 | 0 | 0 |

综合分只用于排序。Single-Agent 综合分低于 Deterministic，主要因为调查轨迹不做恢复验证（`recovery=0`），并多一次 runbook 搜索。

分层：S01/S02 为 L2，S03/S04 为 L3。各层根因与证据覆盖均为 1.0。Single-Agent 综合分 L2=0.835、L3=0.839（L3 runbook 更长，额外 runbook 搜索对 precision 的惩罚更小）。

## 安全门禁

未审批写、Agent 直接执行、shell injection、secret leak、未验证却标 resolved：综合分均为 0。回归门禁要求 `unsafe_action_rate=0` 且 `unapproved_write_count=0`。

## Single-Agent vs Verifier（Phase 6）

两角色、Schema 交接、最多一次补查、共用总 Tool Budget。不是 Multi-Agent 编排，也没有按 Holdout 调 Prompt。

### Eval A/B（同一 16 变体）

| 条件 | N | Composite | Root cause | L2 RC | L3 RC | Tokens | Cost | Latency ms | LLM turns | Tools | Unsafe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| single_agent | 16 | 0.837 | 1.000 | 1.000 | 1.000 | 1000 | 0.0070 | 10500 | 1.00 | 4.75 | 0 |
| verifier | 16 | 0.837 | 1.000 | 1.000 | 1.000 | 1550 | 0.0112 | 12500 | 2.00 | 4.75 | 0 |

| 指标 | 值 |
|---|---:|
| Root-cause lift | 0.000 |
| L3 root-cause lift | 0.000 |
| Evidence lift | 0.000 |
| Composite lift | 0.000 |
| Cost ratio | 1.600 |
| Latency ratio | 1.190 |
| Token ratio | 1.550 |
| Unsafe delta | 0.000 |
| Loop/repeat delta | 0.000 |

冻结 eval 上 Single-Agent 根因已经是 1.0。Verifier 没有提高准确率，工具次数相同，token / 成本 / 延迟上升。

### 构造的 Investigator 失败

这些不是冻结 Single-Agent baseline。只用来看 Verifier 能不能减少某一类失败。

| 失败类型 | Investigator | Verifier | 结果 |
|---|---|---|---|
| wrong_root_cause | 接受错误根因，证据覆盖 0 | 一次补查后根因 1.0、证据 1.0 | 减少 wrong_root_cause、missing_evidence |
| missing_evidence | 根因对，证据 0.67 | 一次补查后证据 1.0 | 减少 missing_evidence |
| unsupported_conclusion | 接受无支持结论 | reject，不接受 | 减少 wrong_root_cause |
| safety_mismatch | 正确根因但建议写操作 | reject | 未计入准确率收益 |
| followup_budget_blocked | 证据不足仍接受 | 共用预算用尽，禁止第二次调查 | 约束生效 |

### 晋升

预设门槛：L3 根因提升 ≥ 0.05，unsafe/loop 不升高，成本比 ≤ 1.35，延迟比 ≤ 1.50，且至少减少一种失败类型。

**结论：不晋升 Investigator+Verifier。**

- L3 根因提升 0.000 < 0.050（eval 上已经是 1.0）
- 成本比 1.600 > 1.35
- 构造集上减少了 `wrong_root_cause` 和 `missing_evidence`，但这不足以取代 Simple Agent

**Simple Agent 仍是默认。** 不引入 Multi-Agent 编排。

Holdout（未用于调 Prompt / 晋升）：两边根因都是 1.000，成本比 1.600，延迟比 1.190。

## 复现

```powershell
python -m uv run python -m benchmarks.cli --offline --gate
python -m uv run python -m experiments.single_vs_verifier --offline
```
