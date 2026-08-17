---
name: incident-scenario
description: Design reproducible incident scenarios with fault injection, hidden ground truth, recovery checks, and anti-cheat verification codes. Use when editing simulator/, scenarios, or incident dataset JSON.
---

# Incident scenario

## Schema

Use `IncidentScenario` in `src/opspilot/domain/incidents.py`.

`ground_truth_root_causes` and `verification_code` are scorer-only. Never put them in Agent prompts, tool results, or runbooks.

## First matrix (Phase 1)

| ID | Fault |
|---|---|
| S01 | DB connection pool exhaustion |
| S02 | Redis latency / cache collapse |
| S03 | Bad deployment |
| S04 | Downstream payment timeout |

Later: S05 OOM, S06 missing env, S07 disk full, S08 misleading deploy.

## Design rules

- Service and resource names must not reveal the root cause
- Logs must not say `simulated error`
- Prompts must not contain answer keywords
- Each scenario injects a unique verification code the Agent can only find via tools
- Recovery checks use real APIs/metrics, not LLM judgment
- Inject and reset are idempotent and repeatable

## Implementation shape

```text
inject → emit metrics/logs/traces → agent investigates
reset  → clear fault → recovery checks pass without LLM
```

## Tests

- Scenario integrity (`benchmarks/datasets/check_integrity.py`)
- Two consecutive inject/reset cycles
- Recovery verification without an LLM

## Out of scope

LLM integration, UI, Multi-Agent.
