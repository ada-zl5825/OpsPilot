# Benchmark

对照组：Deterministic Runbook、Single-Agent、可选 Verifier、可选 SFT/DPO。

综合分只用于排序。原始指标必须单独报告。`unsafe_action` 时综合分为 0。

## 数据集规则

- Ground truth 不进 Agent 上下文
- 禁止答案暗示的资源名、日志、prompt
- 每个场景有 verification code
- Prompt / Tool Catalog / 模型变更时切新 baseline
- 保留 Holdout

实现入口：`benchmarks/`。完整性检查：`python -m benchmarks.datasets.check_integrity`。

Phase 3 已能产出可回放轨迹（`artifacts/investigations/`）。完整 scorer / 对照实验仍是 Phase 5。
