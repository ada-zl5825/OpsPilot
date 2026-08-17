# 领域模型

实现位于 `src/opspilot/domain/`。

| 模型 | 职责 |
|---|---|
| `IncidentScenario` | 冻结场景。`ground_truth_root_causes` 仅供 Scorer |
| `IncidentRun` | 一次调查运行，含模型、Prompt/Tool 版本、token、诊断 |
| `Evidence` | 工具证据摘要；原文进 artifact，不进轨迹表 |
| `Hypothesis` | 根因假设与证据引用 |
| `RemediationProposal` | 类型化修复建议 + digest/过期/幂等键 |
| `ApprovalDecision` | 绑定 `proposal_digest` 的人审批 |
| `ExecutionAttempt` | 执行尝试与回滚结果 |
| `AgentEvent` | 可回放轨迹事件 |

Final Diagnosis 必须引用 Evidence ID。未完成恢复验证不得标记 `resolved`（`IncidentRun.recovery_verified` 必须为 true）。

Phase 3 调查运行时：`src/opspilot/investigation/`。轨迹写入 Stream Event Store（内存或 `artifacts/investigations/{run_id}/events.jsonl`），可用 `opspilot replay --run-id` 回放。

Phase 4 修复控制面：`src/opspilot/remediation/`。`RemediationProposal` 经 Policy / Dry Run 后由人审批；批准绑定 `proposal_digest`。执行与回滚只走 control plane，不进 Agent 工具目录。

Phase 6 Verifier：`src/opspilot/verifier/`。Investigator 只通过 `InvestigatorBundle` 交接，不与 Verifier 自由对话。Verifier 输出 `VerifierVerdict`（accept / request_followup / reject）。最多一次补查，与 Investigator 共用总 Tool Budget。Verifier 默认只读，不能拿到 execute/rollback。
