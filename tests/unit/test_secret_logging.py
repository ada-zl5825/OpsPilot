from opspilot.logging import _redact_event
from opspilot.policy.redaction import REDACTED, redact_mapping, redact_secrets


def test_redacts_api_key_and_bearer() -> None:
    text = "api_key=sk-secret token=abc Bearer abcdef.123"
    result = redact_secrets(text)
    assert "sk-secret" not in result
    assert "Bearer abcdef.123" not in result
    assert REDACTED in result


def test_redact_mapping_strips_sensitive_keys() -> None:
    payload = {
        "azure_api_key": "super-secret",
        "nested": {"authorization": "Bearer aaa.bbb"},
        "note": "api_key=visible-secret",
    }
    redacted = redact_mapping(payload)
    assert redacted["azure_api_key"] == REDACTED
    assert redacted["nested"]["authorization"] == REDACTED
    assert "visible-secret" not in redacted["note"]


def test_log_processor_redacts_event_dict() -> None:
    redacted = _redact_event(
        None,
        "info",
        {"event": "connecting", "azure_api_key": "abc123", "note": "token=leak"},
    )
    assert redacted["azure_api_key"] == REDACTED
    assert "abc123" not in str(redacted)
    assert "token=leak" not in str(redacted)
