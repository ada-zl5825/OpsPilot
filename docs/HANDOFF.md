# OpsPilot 交接文档（新窗口从这里开始）

更新时间：2026-08-17  
作者：李智峰  
仓库：https://github.com/ada-zl5825/OpsPilot  
Holmes 上游 fork：https://github.com/ada-zl5825/holmesgpt

**新窗口第一件事：读本文件 + `AGENTS.md` + `skills/incident-scenario/SKILL.md`，然后做 Phase 1。不要重做 Phase 0。**

## 当前状态

**Phase 0 已完成，且已用真实 Azure + Holmes 容器验收。**

| 门禁 | 结果 |
|---|---|
| Holmes `/healthz` | `{"status":"healthy"}` |
| Azure `/api/chat` | 通，模型 `azure/Opspilot-gpt-4o` |
| MCP `lab_status` | Holmes 实际调用，最终回答含 `OP-P0-LAB` |
| `lab_mutate_probe` + `enable_tool_approval` | stream 停在 `approval_required`，`unapproved_write_attempted=false` |
| 离线 unit + contract | 通过 |

详细记录：`docs/UPSTREAM_BASELINE.md`。

**下一步是 Phase 1：事故模拟环境（S01–S04）。不接 LLM，不做 UI / Multi-Agent / SFT。**

## 新窗口开场 Prompt（可直接粘贴）

```text
先读 docs/HANDOFF.md、AGENTS.md、skills/incident-scenario/SKILL.md。
Phase 0 已完成，不要重做 Holmes 基线。

$incident-scenario

实现 OpsPilot 微服务事故模拟 MVP。使用 Docker Compose，包含 gateway、checkout、
payment、inventory、PostgreSQL、Redis、Prometheus、Loki、Tempo 和 OTel Collector。
实现 S01 数据库连接池耗尽、S02 Redis 延迟、S03 错误部署、S04 下游支付超时。
每个场景必须提供 inject、reset、ground truth、required evidence、allowed remediation、
recovery checks 和 anti-cheat verification code。故障和恢复必须可重复、幂等；
不得在资源名、日志或 prompt 中暴露根因。

不接 LLM。完成后运行场景完整性测试、两次连续 inject/reset 和真实恢复验证。
```

## 硬约束（违反即做错）

1. 不要把 HolmesGPT 源码拷进本仓库。
2. 写操作只能走 Proposal → Policy → Approval → Executor。
3. Agent 永远不能拿到 `execute_approved_proposal`。
4. 禁止任意 Shell 字符串；动作必须是 typed command。
5. Ground truth / verification code 不能进 Agent prompt、tool result、runbook。
6. 不要记日志里的 token、密钥、kubeconfig、完整敏感日志。
7. 不要提交 `.env`。
8. 不要开始 Multi-Agent / SFT。Phase 1 也不要接 LLM。
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

## 常用命令

```powershell
python -m uv sync --extra dev
python -m uv run pytest tests/unit tests/contract -q
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

Makefile 等价：`make test`、`make holmes-up`、`make holmes-smoke`。Windows 上若没 make，直接跑上面的 python/docker 命令。

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
| `simulator/` | **Phase 1 主战场（现在几乎是空 README）** |
| `src/opspilot/domain/incidents.py` | `IncidentScenario` schema，含 scorer-only ground truth |
| `docker-compose.yml` | 现在只有 postgres + holmes + lab MCP |

## Phase 1 验收（做完必须满足）

- 一条命令拉起模拟栈（可在现有 compose 上加 profile，不要破坏 holmes profile）。
- S01–S04 各自：inject、reset、ground truth、required evidence、allowed remediation、recovery checks、anti-cheat verification code。
- 故障与恢复可重复、幂等；连续两次 inject/reset 都过。
- 指标、日志、Trace 有真实数据（Prometheus / Loki / Tempo）。
- **不调用 LLM** 也能确定性验证故障与恢复。
- 服务名、日志、prompt **不得泄露根因**（不要写 `simulated error`、不要用 `broken-payment` 这种名字）。
- verification code 只能通过工具/观测数据被 Agent 日后发现，不能写进 prompt 或 runbook。

场景表：

| ID | 故障 |
|---|---|
| S01 | 数据库连接池耗尽 |
| S02 | Redis 延迟 / 缓存塌陷 |
| S03 | 错误部署 |
| S04 | 下游支付超时 |

完整设计：`OpsPilot_完整开发技术文档.md` 的 Phase 1 章节。

## 不要做

- 不要重跑/重写 Phase 0 Holmes client，除非 compose 被你改坏了。
- 不要把 observability MCP（Phase 2）和模拟器混在一次大 PR 里；Phase 1 只建环境和场景。
- 不要给 Agent 容器挂可写 kube 凭证。
- 不要把 `.env`、密钥、真实 Azure endpoint 写进文档或 commit。
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
