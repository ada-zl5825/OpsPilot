# 诊断打分层：研究结论与实现契约

记录时间：2026-08-17  
范围：Phase 5 scorer-only 诊断契约。不重做 Phase 0–6，不改 lab / MCP / Holmes pin，不开始 UI / Multi-Agent / SFT。  
前置：`docs/09_LIVE_AZURE_INVESTIGATION_FIX.md`、`docs/10_LIVE_EMPTY_EVIDENCE_FIX.md`。  
控制面结论不变：unsafe 0、hard fail 0；下一刀是打分与诊断，不是 rebuild。

## 1. 问题

Live 工具已经能读到真实日志/指标，模型不再写成「没有错误」。根因分仍是 0，因为 scorer 在比冻结 slug，模型在写观察句。S02–S04 还容易收成同一套 DB 叙事。

对照 live Single-Agent `artifacts/benchmarks-live/d89121a4-4f24-4e50-bcdf-fe02886f5e81`：

| 场景 | 冻结 slug | 模型原文 | 旧分 | 判断 |
|---|---|---|---:|---|
| S01 | `checkout_database_connection_pool_exhausted` | checkout 因 database connection wait 超过 deadline 而 5xx | 0 | **假 0**：机制已接近，缺 `pool` / `exhausted` |
| S02 | `redis_cache_lookup_latency` | 同一套 DB connection wait | 0 | **真 0**：收成 DB 叙事 |
| S03 | `checkout_regression_in_release_1_4_2` | 点名 1.4.2 @ 14:44，但又夹了 DB wait | 0 | **假 0**：发布回归已点到，被 token 集合卡死 |
| S04 | `payment_downstream_deadline_exceeded` | DB 问题 + 笼统 downstream timeout | 0 | **真 0**：没钉到 payment |

Verifier `d83f0a51` 也没抬根因：S01/S03/S04 拒成 `diagnosis_root_cause=null`，S02 把「DB + 一句 cache delay」accept 掉。

旧匹配在 `root_cause_scores`：规范化后整串相等给 1.0；否则「truth 是子串 / truth 全部 token ⊆ 预测」给 0.5。综合分用后者。离线 1.0 是因为冻结轨迹直接抄 slug。

证据覆盖也偏松：`required_evidence.description` 没用上，只看有没有打过 prometheus/loki/tempo。所以 S01–S03 证据能到 1.0，根因仍是 0。

## 2. 查阅的 2026 资料

共识已经从「一句自由文本对答案」变成结构化、可观察、过程可核。

| 来源 | 要点 | 链接 |
|---|---|---|
| AIOps2025 / RCA100 | Localization / Identification / Reason 三轴（约 0.40 / 0.40 / 0.20）。RCA100 四层 GT：故障类、根因实体、因果链、每步 checkpoint | https://arxiv.org/html/2606.29193v1 |
| OpenRCA 2.0 | 对观察得到的 fault-kind 打分，不对混沌 API 名。Agent 输出 `(service, fault_kind)`。AnySvc 可到 76%，pair F1 掉到 34%——服务对了、机制标错 | https://arxiv.org/html/2606.27154v1 |
| ITBench-Evaluations | `ROOT_CAUSE_ENTITY` 与 `ROOT_CAUSE_REASONING`（0 / 0.5 / 1）分开；下游症状对了可给部分分 | https://github.com/itbench-hub/ITBench-Evaluations |
| ITBench-AA | 漏一个 GT 实体该题 0；frontier 仍低于 50% | https://huggingface.co/blog/ibm-research/itbench-aa |
| GALA+ SURE-Score | 自由文本用 Yes/No checklist，不用 BLEU/ROUGE；judge 必须和被评模型不同 | https://arxiv.org/html/2608.08968 |
| ORCA-bench | LLM-as-judge，人工复标 κ=0.90；中等难度最好约 25% | https://arxiv.org/html/2607.28545 |
| Waterloo RCA failures | Location / Type / Hypothesis 分开报。RF-03：把症状观察者当成根因——即 S02–S04 的 DB 塌缩 | https://arxiv.org/html/2601.22208 |

本仓库规格本来就有 Exact Match / Semantic Match（`OpsPilot_完整开发技术文档.md` §12.2）。Semantic 被实现成 token 子集，所以 live 全灭。

## 3. 结论（先打分，再谈诊断质量）

1. 不要把 slug / 四个故障名写进 prompt 来抬分。
2. 不要 rebuild lab / MCP。
3. 不要用 LLM judge 进 v1 综合分；judge 最多做旁路。
4. 不要在 Holdout 上调 alias 后宣称泛化。
5. 假 0（S01/S03）和真塌缩（S02/S04）必须能分开。一个 slug 分做不到。
6. 改综合分含义必须切新 baseline。本次 **不改 v1 综合分公式，也不改 `evidence_coverage` 的 source_system 语义**，以免离线门禁误伤。根因分改为：slug 全等仍 1.0；否则走 rubric 分解分。

## 4. 实现契约

`IncidentScenario.diagnosis_rubric` 只供 Scorer。永不进 Agent prompt、tool result、runbook、InvestigatorBundle。

```text
diagnosis_rubric:
  entity            根因实体（checkout / redis / payment / checkout_release）
  fault_kind        可观察故障类（不是作者内部 slug）
  entity_aliases    定位用短语；S02/S04 不能只靠 checkout
  accept_any        观察等价（connection wait ≈ pool exhausted）
  reject_if_primary 竞争性 attractor；出现且没有 accept 则 Identification=0
  evidence_checkpoints[]
    source_system
    must_match[]    命中任一短语即可
```

根因分：

```text
if slug 规范化全等:
    exact = 1.0, score = 1.0
else if 有 rubric:
    localization    = 1 if 任一 entity_alias 出现在诊断里 else 0
    identification  = 1 if accept_any 且无 attractor
                    = 0.5 if accept_any 且有 attractor（主因被污染）
                    = 0 otherwise
    reason          = 诊断文本命中的 checkpoint 比例
    score = 0.40*localization + 0.40*identification + 0.20*reason
else:
    旧 token 子集 / 子串 → 0.5 或 0
```

原始指标多报：`root_cause_localization`、`root_cause_identification`、`root_cause_reason`、`evidence_checkpoint_coverage`。

`evidence_coverage` 仍按 source_system 计（v1 门禁）。`evidence_checkpoint_coverage` 扫成功 tool result 是否出现 checkpoint 短语；离线通用摘要通常为 0，不进综合分。

## 5. 用现有 live 原文做的预期（不重跑 Azure）

| 诊断 | Localization | Identification | Reason | 新 root_cause_score |
|---|---:|---:|---:|---:|
| S01 connection wait / deadline | 1 | 1 | ≥0.5 | ≥0.8 |
| S02 纯 DB wait | 0 | 0 | 0 | 0 |
| S03 1.4.2 + DB wait | 1 | 0.5 | ≥0.5 | ≥0.7 |
| S04 DB + 笼统 downstream timeout | 0 | 0 | 0 | 0 |

S02/S04 该还是低：那是诊断质量，不是 matcher 误杀。抬真实根因是下一步（结构化诊断字段 / Verifier 对照 rubric），不是本层。

## 6. 明确不做

- 不把 `db_pool_*` / 四个 slug 写进 prompt
- 不晋升 Verifier，不加 Multi-Agent
- 不把 LLM judge 写入 v1 综合分
- 不改 Holmes pin，不 rebuild 模拟栈
- 不在 Holdout 上调 Prompt / alias

S02–S04 真塌缩的连跑残留（Loki/Prom 上场窗口）见 `docs/12_LIVE_CROSS_SCENARIO_RESIDUE.md`。30s slack 仍吃尾部时见 `docs/13_LIVE_QUIET_BEFORE_INJECT.md`。

## 7. 如何复验

```powershell
python -m uv run pytest tests/unit/test_eval_scorer.py tests/unit/test_scenario_dataset.py tests/contract/test_investigation_prompt_integrity.py -q
python -m uv run python -m benchmarks.datasets.check_integrity
python -m uv run python -m benchmarks.cli --offline --gate
```

离线 Deterministic 综合分仍须 1.0，Single-Agent 根因仍须 1.0（冻结轨迹抄 slug）。Prompt / bundle 仍不得出现 rubric 短语与 slug。
