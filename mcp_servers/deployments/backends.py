from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from mcp_servers.common.errors import BackendError
from mcp_servers.common.time_range import TimeWindow, parse_iso8601
from mcp_servers.deployments.store import load_json


class DeploymentBackend(Protocol):
    def list_deployments(
        self, service: str, window: TimeWindow, limit: int
    ) -> list[dict[str, Any]]: ...

    def compare(
        self, service: str, from_version: str, to_version: str
    ) -> dict[str, Any] | None: ...

    def ci_failures(
        self, service: str, window: TimeWindow, workflow: str, limit: int
    ) -> list[dict[str, Any]]: ...


class CatalogBackend:
    def list_deployments(
        self, service: str, window: TimeWindow, limit: int
    ) -> list[dict[str, Any]]:
        rows = list(load_json("catalog.json").get("deployments", []))
        return _filter_deployments(rows, service, window, limit)

    def compare(self, service: str, from_version: str, to_version: str) -> dict[str, Any] | None:
        key = f"{service}:{from_version}:{to_version}"
        payload = load_json("diffs.json").get(key)
        return payload if isinstance(payload, dict) else None

    def ci_failures(
        self, service: str, window: TimeWindow, workflow: str, limit: int
    ) -> list[dict[str, Any]]:
        rows = []
        for item in load_json("ci_failures.json").get("failures", []):
            if item.get("service") != service:
                continue
            if workflow and item.get("workflow") != workflow:
                continue
            failed_at = parse_iso8601(str(item["failed_at"]))
            if window.start <= failed_at <= window.end:
                rows.append(item)
        return rows[:limit]


class LiveDeploymentBackend:
    """Reads lab /releases and /version. Diffs and CI stay on the local catalog."""

    def __init__(self, timeout: float) -> None:
        self._timeout = timeout
        self._catalog = CatalogBackend()
        self._urls = {
            "checkout": os.environ.get("CHECKOUT_URL", "http://127.0.0.1:8081"),
            "payment": os.environ.get("PAYMENT_URL", "http://127.0.0.1:8082"),
            "gateway": os.environ.get("GATEWAY_URL", "http://127.0.0.1:8080"),
            "inventory": os.environ.get("INVENTORY_URL", "http://127.0.0.1:8083"),
            "notification": os.environ.get("NOTIFICATION_URL", "http://127.0.0.1:8084"),
        }

    def list_deployments(
        self, service: str, window: TimeWindow, limit: int
    ) -> list[dict[str, Any]]:
        names = [service] if service != "all" else list(self._urls)
        collected: list[dict[str, Any]] = []
        errors = 0
        for name in names:
            try:
                collected.extend(self._service_history(name))
            except BackendError:
                errors += 1
        if errors == len(names) and not collected:
            raise BackendError(
                "deployment services unreachable",
                suggested_fix="start the lab profile or use OPSPILOT_MCP_BACKEND=fake",
            )
        return _filter_deployments(collected, service, window, limit)

    def compare(self, service: str, from_version: str, to_version: str) -> dict[str, Any] | None:
        return self._catalog.compare(service, from_version, to_version)

    def ci_failures(
        self, service: str, window: TimeWindow, workflow: str, limit: int
    ) -> list[dict[str, Any]]:
        return self._catalog.ci_failures(service, window, workflow, limit)

    def _service_history(self, service: str) -> list[dict[str, Any]]:
        base = self._urls[service].rstrip("/")
        if service == "checkout":
            payload = _get_json(f"{base}/releases", self._timeout)
            return _from_checkout_releases(payload)
        payload = _get_json(f"{base}/version", self._timeout)
        return [
            {
                "service": service,
                "version": str(payload.get("version", "unknown")),
                "git_sha": str(payload.get("git_sha", "")),
                "released_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "status": "success",
                "actor": "lab",
                "changed_services": [service],
            }
        ]


def _from_checkout_releases(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload.get("history", []):
        rows.append(
            {
                "service": "checkout",
                "version": item.get("version"),
                "git_sha": item.get("git_sha", ""),
                "released_at": item.get("released_at"),
                "status": "success",
                "actor": "release-bot",
                "changed_services": ["checkout"],
            }
        )
    for neighbor in payload.get("neighbors", []):
        rows.append(
            {
                "service": neighbor.get("service"),
                "version": neighbor.get("version"),
                "git_sha": neighbor.get("git_sha", ""),
                "released_at": neighbor.get("released_at"),
                "status": "success",
                "actor": "release-bot",
                "changed_services": [neighbor.get("service")],
            }
        )
    return rows


def _filter_deployments(
    rows: list[dict[str, Any]], service: str, window: TimeWindow, limit: int
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in rows:
        if service != "all" and item.get("service") != service:
            continue
        released = parse_iso8601(str(item["released_at"]))
        if window.start <= released <= window.end:
            filtered.append(item)
    filtered.sort(key=lambda item: str(item.get("released_at", "")), reverse=True)
    return filtered[:limit]


def _get_json(url: str, timeout: float) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        raise BackendError(
            f"backend unreachable: {type(exc).__name__}",
            suggested_fix="start the lab services and retry",
        ) from exc
    if response.status_code >= 400:
        raise BackendError(f"backend HTTP {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise BackendError("backend returned a non-object payload")
    return payload
