# Deterministic vs Single-Agent

Phase 5 offline comparison. Frozen scores live in `benchmarks/baselines/v1/`.

```powershell
python -m uv run python -m benchmarks.cli --offline --gate
```

Do not tune prompts against the holdout split (`S0x-V05`).
