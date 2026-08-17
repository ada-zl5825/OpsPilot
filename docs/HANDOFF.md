# OpsPilot 交接文档（新窗口从这里开始）

更新时间：2026-08-17  
作者：李智峰  
仓库：https://github.com/ada-zl5825/OpsPilot  
Holmes 上游 fork：https://github.com/ada-zl5825/holmesgpt

**新窗口第一件事：读本文件 + `AGENTS.md` + `skills/agent-eval/SKILL.md`。Phase 0–6 已完成。不要重做 Phase 0–6，不要开始 UI / Multi-Agent 编排 / SFT。**

## 当前状态

**Phase 0 已完成**（真实 Azure + Holmes 容器）。记录：`docs/UPSTREAM_BASELINE.md`。

**Phase 1 已完成**（S01–S04 模拟栈，不接 LLM）。

**Phase 2 已完成**（Observability / Deployment / Runbook MCP，只读）。

**Phase 3 已完成**（Single-Agent 调查基线）。实现：`src/opspilot/investigation/`。

**Phase 4 已完成**（安全修复控制面）。实现：`src/opspilot/remediation/`、`mcp_servers/remediation/`。

**Phase 5 已完成**（Benchmark v1）。实现：`src/opspilot/eval/`、`benchmarks/`。报告：`docs/08_EXPERIMENT_REPORT.md`。

**Phase 6 已完成**（Verifier 实验）。实现：`src/opspilot/verifier/`、`experiments/single_vs_verifier/`。结论：不晋升，Simple Agent 仍是默认。

| 门禁 | 结果 |
|---|---|
| `python -m benchmarks.datasets.check_integrity` | `dataset integrity ok (4 scenarios, 20 variants, 4 holdout)` |
| `python -m simulator.harness --cycles 2` | S01–S04 各两轮 inject/reset/recovery 全过 |
| Prometheus `sum(http_requests_total)` | 有真实计数 |
| Loki `{service_name="checkout"}` | 有场景日志（含 request_id token） |
| Tempo `/api/search` | 有 checkout/payment span |
| `holmes` profile | 未破坏；可与 `lab` 同时运行 |
| Phase 2 unit + contract | `tests/unit` + `tests/contract`（含 Azure schema suite） |
| Phase 3 unit + contract | S01–S04 prompt 无 GT；Final Diagnosis 必须引用 Evidence ID；轨迹可回放；重复 tool/失败结果不能标成功 |
| Phase 4 unit + contract + security | 未批准/篡改/过期/跨 ns/digest 不匹配均不能写；Agent 看不到 execute/rollback；typed command only |
| Phase 5 offline + gate | 20 变体（16 eval / 4 holdout）；Deterministic 综合分 1.0；Single-Agent 0.8372；unsafe/未审批写综合分 0 |

Live Azure 调查曾因可选参数 `null` 被 FastMCP 拒绝、以及按工具名计重复预算而失败。修复记录：`docs/09_LIVE_AZURE_INVESTIGATION_FIX.md`。随后根因仍为 0，是因为空序列被当成健康信号。修复记录：`docs/10_LIVE_EMPTY_EVIDENCE_FIX.md`。Verifier 不得把 Investigator 查到的措辞（例如 “connection pool”）当成 prompt 泄题。空证据修好后，根因仍为 0 是因为自然语言对不上冻结 slug，且 S02–S04 易收成同一套 DB 叙事。研究与契约：`docs/11_DIAGNOSIS_SCORING.md`。Scorer 现用 `diagnosis_rubric`。Live 连跑会把 S01 的 Loki/Prom 带进后三场 10 分钟窗；本场 onset 裁窗见 `docs/12_LIVE_CROSS_SCENARIO_RESIDUE.md`。不要据此重做 Phase 0–6 或开始 Multi-Agent。

**下一步不要做 UI / Multi-Agent 编排 / SFT。Phase 7 仅在轨迹数据集与 Benchmark 继续冻结且明确要求时才开始。真要抬 S02–S04 的真实根因，是诊断 JSON / Verifier 对照 rubric，不是 rebuild。**

## 新窗口开场 Prompt（可直接粘贴）

```text
先读 docs/HANDOFF.md、AGENTS.md、skills/agent-eval/SKILL.md。
Phase 0–5 已完成。不要重做 Holmes 基线、模拟器、Phase 2 MCP、Single-Agent 调查、
安全修复控制面或 Benchmark v1。

Phase 0–6 已完成。不要重做 Holmes 基线、模拟器、Phase 2 MCP、Single-Agent 调查、
安全修复控制面、Benchmark v1 或 Verifier 实验。

不要开始 UI、Multi-Agent 编排或 SFT。
```

## 硬约束（违反即做错）

1. 不要把 HolmesGPT 源码拷进本仓库。
2. 写操作只能走 Proposal → Policy → Approval → Executor。
3. Agent 永远不能拿到 `execute_approved_proposal`。
4. 禁止任意 Shell 字符串；动作必须是 typed command。
5. Ground truth / verification code 不能进 Agent prompt、tool result、runbook。
6. 不要记日志里的 token、密钥、kubeconfig、完整敏感日志。
7. 不要提交 `.env`。
8. 不要开始 Multi-Agent 编排 / SFT。Phase 6 的两角色实验不是编排器。Phase 1 也不要接 LLM。
9. 不要改 git config。上游 PR 才需要 DCO `Signed-off-by`（只在 holmesgpt fork 上）。

## 本机环境

- Windows + PowerShell。`&&` 在旧 PowerShell 里不可用，用 `;`。
- Python 3.12。`uv` 不在 PATH，一律用 `python -m uv`。
- Docker Desktop 已装。若 `docker` 找不到，先刷新 PATH：

```powershell
$machine = [Environment]::GetEnvironmentVariable("Path","Machine")
$user = [Environment]::GetEnvironmentVariable("Path","User")
$env:Path = "$machine;$user"
```

- 本地密钥只在 `.env`（已 gitignore）。不要打印 endpoint / API key。
- `AZURE_OPENAI_DEPLOYMENT` 必须是 Azure **部署名**，当前是 `Opspilot-gpt-4o`，不是模型族名 `gpt-4o`。
- `AZURE_OPENAI_ENDPOINT` 必须是资源根 `https://<resource>.openai.azure.com`，**不要**带 `/openai/v1` 或 `/openai/deployments/...`。

## Holmes pin（不要改，除非先跑兼容测试）

- Image：`robustadev/holmes:0.39.0`
- Digest：`sha256:035bb9f788c8a5df851b023d6b3be21384bff75b4496299a547fbf52b0fb67d8`
- 文件：`config/holmesgpt.pin`
- HTTP：`http://localhost:5050`（`/healthz`、`/api/chat`）
- Lab MCP：`http://localhost:8000/mcp`（容器内 Holmes 走 `http://opspilot-mcp:8000/mcp`）
- Phase 2 MCP：observability `8001`、deployments `8002`、runbooks `8003`
- Phase 4 MCP：remediation `8004`（只有 propose / dry-run / verify；无 execute）

## Phase 0 踩坑（改 Holmes / Azure 时必看）

1. **镜像 ENTRYPOINT 是 CLI**（`python holmes_cli.py`）。Compose 必须覆盖：`entrypoint: ["python", "-u", "server.py"]`。
2. **0.39.0 忽略 `HOLMES_CONFIG_PATH`**。把 `config/holmes/config.yaml` 挂到 `/root/.holmes/config.yaml`。
3. **`model_list.yaml` 挂到 `/etc/holmes/model_list.yaml`**，用 `MODEL_LIST_FILE_LOCATION`。
4. LiteLLM 的 `azure/<name>` 里，`<name>` 是 **Azure deployment name**。
5. Holmes 默认会要 `max_tokens=64000`，gpt-4o 上限 16384。已在 `config/holmes/model_list.yaml` 设 `max_tokens: 4096`，Compose 里有 `OVERRIDE_MAX_OUTPUT_TOKEN=4096` 和 `OVERRIDE_MAX_CONTENT_SIZE=128000`。
6. **`health_check_tool` 不是 0.39.0 `RemoteMCPToolset` 的合法字段**。加了会整组 MCP 加载失败（`Extra inputs are not permitted`）。不要加回去。
7. FastMCP 1.29 的 `run()` 只收 `transport`。host/port 写 `mcp.settings`。必须关掉 DNS rebinding，否则 Holmes 用 `opspilot-mcp` 主机名连不上。
8. `approval_required_tools: [lab_mutate_probe]` 已验证有效。OpsPilot client **禁止** `auto_approve` 和 `approved=true`。
9. Builtin `internet` 已开；k8s / docker / bash 已关，否则容器会因缺 kubeconfig 出问题。
10. 改完 Holmes config 后要 `docker compose --profile holmes up -d --force-recreate holmes`，只 restart 可能还用旧配置。
11. **Azure / gpt-4o 会对未使用的可选工具参数发 JSON `null`。** Schema 不能写成 `str | None`（Azure 拒 `anyOf`），必须在运行时丢掉 null。见 `docs/09_LIVE_AZURE_INVESTIGATION_FIX.md`。改完 MCP 后要 `--build` 重建 `opspilot-observability` 等容器。

## 常用命令

```powershell
python -m uv sync --extra dev
python -m uv run pytest tests/unit tests/contract tests/security -q
python -m uv run python -m opspilot.holmes.smoke

# Docker 找不到时先刷新 PATH，见上文
docker compose --profile holmes up -d --build
docker compose --profile holmes logs holmes --tail 40
# 期望看到：✅ Toolset opspilot_lab

python -m uv run python scripts/dump_live_answer.py
# 期望：tool_names 含 lab_status，analysis 含 OP-P0-LAB

python -m uv run python scripts/dump_live_approval.py
# 期望：paused=true，pending=["lab_mutate_probe"]，unapproved_write_attempted=false
```

Phase 1 lab：

```powershell
docker compose --profile lab up -d --build
python -m uv run python -m benchmarks.datasets.check_integrity
python -m uv run python -m simulator.harness --cycles 2
# 或：$env:OPSPILOT_REQUIRE_LAB="1"; python -m uv run pytest tests/simulator -q
```

Phase 5（不接 LLM）：

```powershell
python -m uv run python -m benchmarks.cli --offline --gate
python -m uv run pytest tests/benchmark -q
```

Phase 6（不接 LLM）：

```powershell
python -m uv run python -m opspilot.cli verify --all --prompt-only
python -m uv run python -m experiments.single_vs_verifier --offline
```

Makefile 等价：`make test`、`make holmes-up`、`make holmes-smoke`、`make lab-up`、`make lab-verify`、`make investigate-prompt`、`make benchmark-offline`、`make verifier-prompt`、`make verifier-ab`。Windows 上若没 make，直接跑上面的 python/docker 命令。

Phase 3（不接 LLM 也可验 prompt / 回放门禁）：

```powershell
python -m uv run python -m opspilot.cli investigate --all --prompt-only
python -m uv run pytest tests/unit/test_investigation_runner.py tests/contract/test_investigation_prompt_integrity.py -q
```

集成测试（可选）：

```powershell
$env:OPSPILOT_REQUIRE_HOLMES="1"
python -m uv run pytest tests/integration -q
```

## 代码地图

| 路径 | 作用 |
|---|---|
| `src/opspilot/holmes/client.py` | Holmes HTTP client；永不自动批准 |
| `src/opspilot/holmes/stream_parser.py` | SSE → `AgentEvent` |
| `src/opspilot/holmes/sse.py` | SSE 分帧 |
| `src/opspilot/holmes/smoke.py` | 健康检查 + 强制 `lab_status` / `OP-P0-LAB` |
| `src/opspilot/holmes/compatibility.py` | Azure tool schema / catalog isolation |
| `src/opspilot/policy/redaction.py` | 日志脱敏 |
| `config/holmes/config.yaml` | toolsets + MCP + approval |
| `config/holmes/model_list.yaml` | Azure 模型与 token 上限 |
| `mcp_servers/lab/` | Phase 0 echo MCP |
| `mcp_servers/common/` | Phase 2 共享运行时（错误、时间范围、预算、artifact） |
| `mcp_servers/observability/` | metrics / logs / traces（禁止任意 PromQL） |
| `mcp_servers/deployments/` | recent / compare / CI summary |
| `mcp_servers/runbooks/` | search_runbooks（untrusted） |
| `simulator/` | Phase 1 微服务、故障注入、观测栈、harness。`GET /v1/active` 只回本场 onset |
| `benchmarks/datasets/incidents/v1/` | S01–S04 场景 JSON（scorer-only ground truth） |
| `src/opspilot/lab/scenarios.py` | 加载 `IncidentScenario` |
| `src/opspilot/domain/incidents.py` | `IncidentScenario` schema，含 scorer-only ground truth |
| `src/opspilot/investigation/` | Phase 3 Single-Agent：prompt、budget、evidence、diagnosis、event store、replay、runner |
| `src/opspilot/eval/` | Phase 5 scorer：slug 全等 + `diagnosis_rubric` 分解分、综合分、hard fail、offline replay |
| `benchmarks/` | Phase 5 harness、20 变体、Deterministic / Single-Agent baseline、regression gate |
| `src/opspilot/verifier/` | Phase 6：InvestigatorBundle、VerifierVerdict、一次补查、共用预算 |
| `experiments/single_vs_verifier/` | Phase 6 Single vs Verifier A/B 与失败分析 |
| `src/opspilot/remediation/` | Phase 4 控制面：propose / policy / dry-run / approve / execute / rollback / verify |
| `src/opspilot/executor/` | typed command、digest、lab/k8s/docker executor（不跑 shell） |
| `src/opspilot/storage/` | IncidentRun / Evidence / Hypothesis / AgentEvent / Proposal / Approval / Execution 表定义 |
| `mcp_servers/remediation/` | Agent-visible propose/dry-run/verify；不注册 execute/rollback |
| `docker-compose.yml` | `postgres` 常开；`holmes` / `lab` 两个 profile |

## Phase 1 已验收

- `docker compose --profile lab up -d --build` 一条命令拉起商店 + 观测栈；`holmes` profile 仍可用。
- S01–S04：inject / reset / ground truth / required evidence / allowed remediation / recovery checks / verification code。
- 连续两轮 inject/reset 幂等；恢复检查打真实 HTTP 与 `/metrics`。
- 指标、日志、Trace 有真实数据。verification code 只出现在观测数据（如 `request_id`），不进 prompt / controller 响应。

| ID | 故障 | 本机复验 |
|---|---|---|
| S01 | 数据库连接池耗尽 | 503 ~1.0s，token 可见，reset 后 200 |
| S02 | Redis 延迟 / 缓存塌陷 | 200 ~2.0s，token 可见，reset 后 <1.2s |
| S03 | 错误部署 | 500，`/version` 回 1.4.1 |
| S04 | 下游支付超时 | 504 ~2.0s，token 可见 |

Controller：`http://localhost:8090/v1/scenarios/{S01}/inject|reset`。响应不含 ground truth。

完整设计：`OpsPilot_完整开发技术文档.md` 的 Phase 1 章节。用法：`simulator/README.md`。

## Phase 2 已验收

- 三个只读 MCP：observability `:8001`、deployments `:8002`、runbooks `:8003`。
- 工具：`query_service_metrics`、`query_service_logs`、`get_trace_summary`、`get_recent_deployments`、`compare_deployments`、`get_ci_failure_summary`、`search_runbooks`。
- 每个工具有 timeout、`max_result_bytes`、结构化错误、服务器端过滤、artifact spilling。
- Azure schema suite：单个坏工具隔离，不丢 catalog。
- Holmes `config/holmes/config.yaml` 已注册三个 Phase 2 toolset。不要加 `health_check_tool`。
- 无写操作、无任意 PromQL/Shell、无 UI。

```powershell
python -m uv run pytest tests/unit tests/contract -q
```

## Phase 3 已验收

- 复用现有 Holmes client 与 Phase 2 只读 MCP；不重写 Agent loop。
- Stream Event Store：`InMemoryInvestigationStore` / `JsonlInvestigationStore`（`artifacts/investigations/{run_id}/events.jsonl`）。
- IncidentRun / Evidence / Hypothesis；Final Diagnosis 必须引用成功 Evidence ID。
- 调查 Prompt 只含 `AgentVisibleIncident`（症状 + 用户报告）。ground truth / verification code / required_evidence 不进 prompt。
- Tool budget、同一 query 重复上限、无进展检测。
- 失败 tool result 不能当成功证据；超预算 / 无进展 / 缺引用 / 写工具尝试都不能标 `diagnosis_complete`。未做恢复验证不能标 `resolved`。
- 轨迹可回放：`opspilot replay --run-id`。
- CLI：`opspilot investigate --scenario S01` / `--all --prompt-only`。
- API：`POST/GET /api/incidents`、`GET /api/incidents/{id}/events`、`POST .../cancel`。不接写执行。

```powershell
python -m uv run python -m opspilot.cli investigate --all --prompt-only
python -m uv run pytest tests/unit tests/contract -q
```

Live Azure 调查（可选，需 lab inject + holmes）：

```powershell
python -m uv run python -m opspilot.cli investigate --scenario S01
```

## Phase 4 已验收

- 写路径：Proposal → Policy → Dry Run → Human Approval → Idempotent Executor → Recovery Verify → Rollback。
- Agent 工具：`propose_*` / `dry_run_remediation` / `verify_recovery`（外加 capabilities / snapshot 只读）。
- Agent **永远没有** `execute_approved_proposal` 或 `rollback_execution`（catalog + FastMCP 都不注册）。
- 批准绑定 `proposal_digest`；参数一变旧批准失效。
- 过期、已执行、被篡改、未批准、跨 namespace、digest 不匹配都不能写。
- Typed command 仅 rollback / restart / scale。禁止任意 Shell / `shell=True` / `--token` `--kubeconfig` `--as`。
- `propose_update_config` 可建 Proposal，policy 拒绝执行。
- Approver 不能是 system Agent；Reject 不能被自动覆盖。
- 同一 Proposal 成功执行最多一次（`idempotency_key` + 锁）。
- API：`POST /api/incidents/{run_id}/proposals`、`/approve`、`/reject`、`/execute`、`/rollback`、`/verify`。execute/rollback 是 control plane，不进 Holmes catalog。
- Holmes `config/holmes/config.yaml` 已注册 `opspilot_remediation`（`:8004`）。不要给它加 mutate 工具。
- 无 UI。

```powershell
python -m uv run pytest tests/unit tests/contract tests/security -q
```

## Phase 5 已验收

- 冻结 20 个场景变体（S01–S04 × V01–V05）。Eval 16，Holdout 4，互不重叠。
- Deterministic runbook baseline 与 Single-Agent offline baseline 已冻结。
- Scorer 报告原始指标；`unsafe_action` / 未审批写成功时综合分为 0。
- 一条 CLI：`python -m benchmarks.cli --offline --gate` → JSON + Markdown。
- Offline replay 可对存储轨迹打分；regression gate 对照 `benchmarks/baselines/v1/manifest.json`。
- Live Azure 仅 `workflow_dispatch` / `--live`，不进普通 PR。
- 无 UI、无 Multi-Agent、无 SFT。

```powershell
python -m uv run python -m benchmarks.datasets.check_integrity
python -m uv run python -m benchmarks.cli --offline --gate
python -m uv run pytest tests/unit tests/contract tests/security tests/benchmark -q
```

## Phase 6 已验收

- Investigator 交接是 `InvestigatorBundle`（Pydantic），不是两段 Agent 自由对话。
- Verifier Prompt / `VerifierVerdict`：accept、request_followup、reject。
- 最多一次补查；Investigator 与 Verifier 共用总 Tool Budget。
- Verifier 默认只读；写工具建议会被 policy 剥掉或拒绝。
- 离线 A/B：同一 16 个 eval 变体上 Single-Agent 与 Verifier 根因都是 1.0；Verifier 增加 token / 成本 / 延迟。
- 构造的 Investigator 失败集上，Verifier 能减少已接受的错误根因和缺证据。
- 晋升条件未满足：**不晋升** Investigator+Verifier。Simple Agent 仍是默认。
- 无 UI、无 Multi-Agent 编排、无 SFT。Holdout 未用于调 Prompt。

```powershell
python -m uv run python -m opspilot.cli verify --all --prompt-only
python -m uv run python -m experiments.single_vs_verifier --offline
python -m uv run pytest tests/unit tests/contract tests/security tests/benchmark -q
```

## 不要做

- 不要重跑/重写 Phase 0 Holmes client，除非 compose 被你改坏了。
- 不要重做 S01–S04 模拟器，除非 lab profile 被你改坏了。
- 不要重做 Phase 2 只读 MCP，除非契约测试被你改坏了。
- 不要重做 Phase 3 调查运行时，除非轨迹/诊断门禁被你改坏了。
- 不要重做 Phase 4 控制面，除非安全门禁被你改坏了。
- 不要重做 Phase 5 Benchmark，除非 scorer / 变体完整性 / regression gate 被你改坏了。
- 不要重做 Phase 6 Verifier，除非 schema / 共用预算 / A/B 报告被你改坏了。不要把两角色实验扩成 Multi-Agent 编排。
- 不要在 Holdout 上调 Prompt 后宣称泛化。
- 不要把 `execute_approved_proposal` 或 `rollback_execution` 注册到 Holmes。
- 不要把写操作 MCP 和只读工具混在一次大 PR 里。
- 不要给 Agent 容器挂可写 kube 凭证。
- 不要把 `.env`、密钥、真实 Azure endpoint 写进文档或 commit。
- 不要把 ground truth / verification code 写进 MCP 工具结果或 runbook。
- 不要 `git push --force`，也不要改 git config。

## 复验记录（2026-08-17，本机）

```text
dump_live_answer.py
  event_types: tool_call, tool_result, llm_end
  tool_names: lab_status
  analysis: ... verification code OP-P0-LAB
  paused: false

dump_live_approval.py
  event_types: tool_call, tool_result, approval_required
  pending: lab_mutate_probe
  paused: true
  unapproved_write_attempted: false
```

Holmes 日志关键行：`✅ Toolset opspilot_lab`，随后 `Running tool #1 lab_status`。

## Phase 1 复验记录（2026-08-17，本机）

```text
dataset integrity ok (4 scenarios)

S01 cycle 1/2: ok  fault=503 token=True recover=True
S02 cycle 1/2: ok  fault=200 ~2.0s token=True recover=True
S03 cycle 1/2: ok  fault=500 token=True recover=True
S04 cycle 1/2: ok  fault=504 token=True recover=True
observability prometheus/loki/tempo: ok
pytest tests/simulator: 1 passed
```

## Phase 4 复验记录（2026-08-17，本机）

```text
pytest tests/unit tests/contract tests/security: 146+ passed
Agent catalog / FastMCP: execute_approved_proposal 与 rollback_execution 均不可见
未批准 / 篡改 / 过期 / 跨 namespace / digest 不匹配 / Shell 与 flag 注入：write_count == 0
并发 execute：同一 execution_id，write_count == 1
```

## Phase 6 复验记录（2026-08-17，本机）

```text
pytest tests/unit tests/contract tests/security tests/benchmark: 190 passed
python -m benchmarks.cli --offline --gate: PASS (deterministic 1.000, single_agent 0.8372)
python -m experiments.single_vs_verifier --offline: DO_NOT_PROMOTE
  eval root_cause lift=0.000  L3 lift=0.000  cost_ratio=1.600  latency_ratio=1.190
  constructed failures reduced: wrong_root_cause, missing_evidence
  Simple Agent remains the default
```

## Phase 5 复验记录（2026-08-17，本机）

```text
dataset integrity ok (4 scenarios, 20 variants, 4 holdout)
deterministic eval: composite=1.000 unsafe=0 hard_fails=0
single_agent eval: composite=0.8372 root_cause=1.0 evidence=1.0 recovery=0.0 unsafe=0
unapproved_write / unsafe_action / secret_leak / resolved_without_verify: composite=0.0
python -m benchmarks.cli --offline --gate: PASS
```
