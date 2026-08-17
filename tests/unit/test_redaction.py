from opspilot.policy.redaction import REDACTED, redact_secrets


def test_redacts_api_key_and_bearer() -> None:
    text = "api_key=sk-secret token=abc Bearer abcdef.123"
    result = redact_secrets(text)
    assert "sk-secret" not in result
    assert "Bearer abcdef.123" not in result
    assert REDACTED in result
