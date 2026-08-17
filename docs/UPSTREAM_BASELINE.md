# Upstream baseline

Status: **Phase 0 complete.** Live Azure ask, MCP `lab_status`, and `approval_required_tools` were verified on 2026-08-17.

## Pin

- Repository: https://github.com/HolmesGPT/holmesgpt
- Fork: https://github.com/ada-zl5825/holmesgpt
- Tag: `0.39.0` (2026-08-10)
- Image: `robustadev/holmes:0.39.0`
- Digest: `sha256:035bb9f788c8a5df851b023d6b3be21384bff75b4496299a547fbf52b0fb67d8`
- HTTP: `http://localhost:5050` (`/healthz`, `/api/chat`)
- Image entrypoint is the CLI (`python holmes_cli.py`). Compose overrides it to `python -u server.py`.

## Checklist

- [x] Holmes image pinned; `:latest` rejected by `build_holmes_runtime_config`
- [x] Container healthy on `http://localhost:5050/healthz` (`{"status":"healthy"}`)
- [x] 0.39.0 reads config from `/root/.holmes/config.yaml` (not `HOLMES_CONFIG_PATH`)
- [x] Lab MCP healthy on `0.0.0.0:8000` (`streamable-http`)
- [x] Stream parser maps `ai_message`, `start_tool_calling`, `tool_calling_result`, `approval_required`, `ai_answer_end`, token usage
- [x] Azure tool schema gate + catalog isolation for a single bad tool
- [x] `approval_required_tools: [lab_mutate_probe]` in `config/holmes/config.yaml`
- [x] Holmes client never auto-approves; `approved=true` is rejected
- [x] `lab_mutate_probe` refuses to write even if invoked
- [x] Secrets are redacted from structured logs
- [x] Live `/api/chat` Azure tool call (`azure/Opspilot-gpt-4o`, `max_tokens: 4096`)
- [x] Live MCP `lab_status` through Holmes; final answer contains `OP-P0-LAB`
- [x] Live Holmes 0.39.0 honors `approval_required_tools` on custom MCP (`lab_mutate_probe` → `approval_required`, `unapproved_write_attempted=false`)

## How to re-verify

Requires a local `.env` (never commit it). Endpoint must be the Azure resource root, not `/openai/v1`. Deployment name is the Azure deployment, not the model family.

```bash
make holmes-up
make holmes-smoke
python -m uv run python scripts/dump_live_answer.py
python -m uv run python scripts/dump_live_approval.py
```

Holmes logs must show `✅ Toolset opspilot_lab`. `dump_live_answer.py` must call `lab_status`. `dump_live_approval.py` must pause on `lab_mutate_probe` and must not execute a write.

## Residual risks

1. **Config path:** 0.39.0 ignores `HOLMES_CONFIG_PATH`. Mount `config/holmes/config.yaml` to `/root/.holmes/config.yaml`.
2. **MCP schema:** do not add `health_check_tool` on `RemoteMCPToolset`; 0.39.0 rejects it (`Extra inputs are not permitted`) and drops the whole `opspilot_lab` toolset.
3. **Token cap:** Holmes default `max_tokens=64000` exceeds gpt-4o (16384). Keep `max_tokens: 4096` in `model_list.yaml` plus compose `OVERRIDE_MAX_OUTPUT_TOKEN`.
4. **Builtin `internet` toolset** is enabled as the read-only builtin. It is not part of the Phase 0 live gate.
5. **Kubernetes toolsets are disabled** so the container can start without a kubeconfig. Re-enable only in a later lab cluster phase.
6. **DCO**: upstream PRs from `ada-zl5825/holmesgpt` must use `Signed-off-by`. Do not change local git config automatically.
7. Holmes may still load other default toolsets. Watch startup logs for unexpected enabled write toolsets.
8. FastMCP DNS rebinding protection is disabled so Holmes can reach `http://opspilot-mcp:8000/mcp` by compose service name.

## DCO on the fork

```bash
git -C <holmesgpt-fork> commit -s -m "..."
```
