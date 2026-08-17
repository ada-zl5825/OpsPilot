from mcp_servers.observability.backends import iter_loki_queries


def test_loki_queries_cover_service_name_and_json_level() -> None:
    queries = iter_loki_queries("checkout", "error", "")
    assert '{service_name="checkout"} |~ "(?i)error"' in queries
    assert '{service="checkout"} |~ "(?i)error"' in queries
    assert any("| json | level=" in item for item in queries)
    assert any("detected_level" in item for item in queries)


def test_loki_queries_omit_severity_filter_when_all() -> None:
    queries = iter_loki_queries("checkout", "all", "")
    assert queries == ['{service_name="checkout"}', '{service="checkout"}']
