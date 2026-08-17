from pathlib import Path

from mcp_servers.common.artifacts import ArtifactStore
from mcp_servers.common.runtime import ToolRuntime
from mcp_servers.runbooks.schemas import POLICY_NOTE
from mcp_servers.runbooks.store import load_runbooks
from mcp_servers.runbooks.tools import search_runbooks


def _runtime(tmp_path: Path) -> ToolRuntime:
    return ToolRuntime(timeout_seconds=5, max_result_bytes=32768, artifacts=ArtifactStore(tmp_path))


def test_search_runbooks_returns_structured_hits(tmp_path: Path) -> None:
    result = search_runbooks(
        {
            "query": "5xx",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "service": "checkout",
            "limit": 5,
        },
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is True
    assert result["untrusted_content"] is True
    assert result["cannot_override_policy"] is True
    assert result["permission_note"] == POLICY_NOTE
    assert result["runbooks"][0]["id"] == "rb-http-5xx"
    assert result["runbooks"][0]["requires_approval_for_fixes"] is True
    assert all(fix["requires_approval"] for fix in result["runbooks"][0]["proposed_fixes"])


def test_search_runbooks_keeps_injection_text_as_data(tmp_path: Path) -> None:
    result = search_runbooks(
        {
            "query": "ignore previous rules",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "service": "gateway",
            "limit": 5,
        },
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is True
    assert result["runbooks"][0]["id"] == "rb-untrusted-example"
    assert result["cannot_override_policy"] is True


def test_search_runbooks_rejects_empty_query(tmp_path: Path) -> None:
    result = search_runbooks(
        {
            "query": "",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
        },
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is False
    assert result["error_type"] == "validation"


def test_runbooks_do_not_contain_ground_truth_or_tokens() -> None:
    forbidden = {
        "checkout_database_connection_pool_exhausted",
        "redis_cache_lookup_latency",
        "checkout_regression_in_release_1_4_2",
        "payment_downstream_deadline_exceeded",
        "OP-S01-M4QX7C",
        "OP-S02-R8NW2H",
        "OP-S03-K2PL9D",
        "OP-S04-T9VC4E",
        "OP-P0-LAB",
    }
    blob = str(load_runbooks()).lower()
    for item in forbidden:
        assert item.lower() not in blob
