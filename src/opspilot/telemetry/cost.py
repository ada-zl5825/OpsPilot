from __future__ import annotations

from decimal import Decimal

from opspilot.domain.incidents import TokenUsage

# Placeholder rates until live pricing is configured. Used only for local estimates.
INPUT_USD_PER_1K = Decimal("0.005")
OUTPUT_USD_PER_1K = Decimal("0.015")


def estimate_cost(usage: TokenUsage) -> Decimal:
    input_cost = (Decimal(usage.input_tokens) / Decimal(1000)) * INPUT_USD_PER_1K
    output_cost = (Decimal(usage.output_tokens) / Decimal(1000)) * OUTPUT_USD_PER_1K
    return (input_cost + output_cost).quantize(Decimal("0.0001"))
