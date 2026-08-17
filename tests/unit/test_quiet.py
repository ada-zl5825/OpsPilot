from simulator.harness.quiet import is_5xx_quiet, loki_value_count, prometheus_scalar


def test_prometheus_scalar_reads_first_sample() -> None:
    payload = {"data": {"result": [{"value": [1755440000, "3.25"]}]}}
    assert prometheus_scalar(payload) == 3.25
    assert is_5xx_quiet(payload) is False


def test_empty_prometheus_result_is_quiet() -> None:
    assert prometheus_scalar({"data": {"result": []}}) == 0.0
    assert is_5xx_quiet({"data": {"result": []}}) is True
    assert is_5xx_quiet({"data": {"result": [{"value": [1, "0.4"]}]}}) is True


def test_loki_value_count_sums_streams() -> None:
    payload = {
        "data": {
            "result": [
                {"values": [["1", "a"], ["2", "b"]]},
                {"values": [["3", "c"]]},
            ]
        }
    }
    assert loki_value_count(payload) == 3
    assert loki_value_count({"data": {"result": []}}) == 0
