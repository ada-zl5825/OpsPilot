# Single-Agent vs Verifier

Phase 6 bounded two-role experiment. Investigator hands off a Pydantic bundle.
Verifier reviews that schema, may request **one** follow-up, and shares the
Investigator tool budget. This is not Multi-Agent orchestration and not SFT.

```powershell
python -m uv run python -m experiments.single_vs_verifier --offline
```

Promotion requires a stable L3 root-cause lift, no unsafe/loop increase,
cost/latency inside caps, and at least one reduced Investigator failure type.
Holdout (`S0x-V05`) is reported only; do not tune the Verifier prompt on it.
