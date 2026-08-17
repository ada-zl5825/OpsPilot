# 架构

OpsPilot 是 HolmesGPT 之上的事故实验与控制面，不重写 Agent Loop。

```text
OpsPilot API / Benchmark Runner
             │
   ├── HolmesGPT API / CLI container   (robustadev/holmes:0.39.0)
   ├── Observability MCP
   ├── Deployment MCP
   ├── Runbook MCP
   ├── Remediation MCP
   └── PostgreSQL / Redis / Prometheus / Loki / Tempo
```

Phase 1 lab topology:

```text
gateway → checkout → inventory
                  → payment
                  → PostgreSQL
                  → Redis
         → notification

controller  inject/reset flags in Redis
traffic     background storefront orders
otel-collector → Loki (logs) + Tempo (traces)
Prometheus scrapes /metrics
```

## 信任边界

- Untrusted：用户输入、日志、Runbook、GitHub 文本、Tool 自然语言
- Semi-trusted：Holmes 输出、根因假设、修复建议
- Trusted deterministic：Pydantic、Policy、Approval、Idempotency、Executor allowlist、Recovery checker、Audit log

LLM 文本不能直接跨越 deterministic boundary 执行写操作。

## 调查状态机

`IncidentCreated → Investigating → RootCauseProposed → VerificationReview → RemediationProposed → AwaitingApproval → Executing → RecoveryVerification → Resolved | RolledBack | HumanEscalation`

## OTel 布局

Phase 3 已挂 `incident.run` / `holmes.investigation`。Phase 4 已挂 `remediation.policy` / `remediation.approval` / `remediation.execute` / `recovery.verify`（无 provider 时为 no-op）。

```text
incident.run
  ├── holmes.investigation
  ├── remediation.policy
  ├── remediation.approval
  ├── remediation.execute
  └── recovery.verify
```
