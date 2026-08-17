from opspilot.executor.idempotency import digest_payload


def test_digest_is_stable_and_order_independent() -> None:
    left = digest_payload({"b": 2, "a": 1})
    right = digest_payload({"a": 1, "b": 2})
    assert left == right
    assert len(left) == 64


def test_digest_changes_when_payload_changes() -> None:
    assert digest_payload({"a": 1}) != digest_payload({"a": 2})
