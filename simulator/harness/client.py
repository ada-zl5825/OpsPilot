from __future__ import annotations

import os
import time
from typing import Any

import httpx


def _json_object(response: httpx.Response) -> dict[str, Any]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("expected JSON object")
    return payload


CONTROLLER_URL = os.environ.get("LAB_CONTROLLER_URL", "http://127.0.0.1:8090")
GATEWAY_URL = os.environ.get("LAB_GATEWAY_URL", "http://127.0.0.1:8080")
CHECKOUT_URL = os.environ.get("LAB_CHECKOUT_URL", "http://127.0.0.1:8081")
PAYMENT_URL = os.environ.get("LAB_PAYMENT_URL", "http://127.0.0.1:8082")
PROMETHEUS_URL = os.environ.get("LAB_PROMETHEUS_URL", "http://127.0.0.1:9090")
LOKI_URL = os.environ.get("LAB_LOKI_URL", "http://127.0.0.1:3100")
TEMPO_URL = os.environ.get("LAB_TEMPO_URL", "http://127.0.0.1:3200")


class LabClient:
    def __init__(self, timeout: float = 8.0) -> None:
        self._http = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._http.close()

    def controller_healthy(self) -> bool:
        try:
            response = self._http.get(f"{CONTROLLER_URL}/healthz", timeout=2.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def inject(self, scenario_id: str) -> dict[str, Any]:
        response = self._http.post(f"{CONTROLLER_URL}/v1/scenarios/{scenario_id}/inject")
        response.raise_for_status()
        return _json_object(response)

    def reset(self, scenario_id: str) -> dict[str, Any]:
        response = self._http.post(f"{CONTROLLER_URL}/v1/scenarios/{scenario_id}/reset")
        response.raise_for_status()
        return _json_object(response)

    def reset_all(self) -> dict[str, Any]:
        response = self._http.post(f"{CONTROLLER_URL}/v1/reset")
        response.raise_for_status()
        return _json_object(response)

    def status(self, scenario_id: str) -> dict[str, Any]:
        response = self._http.get(f"{CONTROLLER_URL}/v1/scenarios/{scenario_id}")
        response.raise_for_status()
        return _json_object(response)

    def place_order(self, timeout: float = 8.0) -> httpx.Response:
        return self._http.post(
            f"{GATEWAY_URL}/api/orders",
            json={"sku": "sku-100", "qty": 1},
            timeout=timeout,
        )

    def checkout_version(self) -> dict[str, Any]:
        return _json_object(self._http.get(f"{CHECKOUT_URL}/version"))

    def checkout_metrics(self) -> str:
        return self._http.get(f"{CHECKOUT_URL}/metrics").text

    def prometheus_query(self, query: str) -> dict[str, Any]:
        response = self._http.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
        response.raise_for_status()
        return _json_object(response)

    def loki_has(self, token: str) -> bool:
        queries = (
            f'{{service_name="checkout"}} |= `{token}`',
            f'{{service_name="payment"}} |= `{token}`',
            f'{{service="checkout"}} |= `{token}`',
        )
        for query in queries:
            try:
                response = self._http.get(
                    f"{LOKI_URL}/loki/api/v1/query",
                    params={"query": query, "limit": "20"},
                    timeout=5.0,
                )
                if response.status_code != 200:
                    continue
                payload = response.json()
                results = payload.get("data", {}).get("result", [])
                if results:
                    return True
            except httpx.HTTPError:
                continue
        return False

    def ready(self, url: str) -> bool:
        try:
            response = self._http.get(url, timeout=2.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def tempo_has_traces(self) -> bool:
        try:
            response = self._http.get(f"{TEMPO_URL}/api/search", params={"limit": "5"}, timeout=5.0)
            if response.status_code != 200:
                return False
            traces = response.json().get("traces", [])
            return bool(traces)
        except httpx.HTTPError:
            return False

    def wait_until(self, predicate: Any, timeout_sec: float, interval: float = 0.4) -> bool:
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(interval)
        return False


def metric_value(metrics_text: str, name: str) -> float | None:
    for line in metrics_text.splitlines():
        if line.startswith("#") or not line.startswith(name):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0] == name:
            return float(parts[1])
    return None
