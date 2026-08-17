from __future__ import annotations

from typing import Any

QUIET_5XX_THRESHOLD = 0.5
QUIET_5XX_RANGE = "1m"
QUIET_ERROR_LOOKBACK_SECONDS = 20
QUIET_WAIT_TIMEOUT_SECONDS = 120
CHECKOUT_5XX_INCREASE = (
    f'sum(increase(http_requests_total{{service="checkout",status=~"5.."}}[{QUIET_5XX_RANGE}]))'
)


def prometheus_scalar(payload: dict[str, Any]) -> float:
    for series in payload.get("data", {}).get("result", []):
        value = series.get("value", [None, "0"])
        if len(value) < 2:
            continue
        try:
            return float(value[1])
        except (TypeError, ValueError):
            continue
    return 0.0


def loki_value_count(payload: dict[str, Any]) -> int:
    total = 0
    for stream in payload.get("data", {}).get("result", []):
        values = stream.get("values", [])
        if isinstance(values, list):
            total += len(values)
    return total


def is_5xx_quiet(payload: dict[str, Any], *, threshold: float = QUIET_5XX_THRESHOLD) -> bool:
    return prometheus_scalar(payload) <= threshold
