"""Unit tests for the audit secret-redaction helper."""

from app.core.redact import redact


def test_plain_values_pass_through():
    assert redact("hello") == "hello"
    assert redact(123) == 123
    assert redact(None) is None


def test_sensitive_keys_redacted_in_flat_dict():
    out = redact({"session_api_key": "sk-secret", "api_key": "abc", "input": "hi"})
    assert out == {"session_api_key": "[REDACTED]", "api_key": "[REDACTED]", "input": "hi"}


def test_nested_structures_walked():
    out = redact(
        {
            "payload": {"session_api_key": "sk-secret", "risk_hints": ["a"]},
            "list": [{"token": "t"}, "plain"],
        }
    )
    assert out["payload"]["session_api_key"] == "[REDACTED]"
    assert out["payload"]["risk_hints"] == ["a"]
    assert out["list"][0]["token"] == "[REDACTED]"
    assert out["list"][1] == "plain"


def test_legit_field_names_preserved():
    out = redact(
        {
            "raw_task": "fix bug",
            "context": "ctx",
            "model": "deepseek-v4-flash",
            "risk_hints": ["data_loss"],
        }
    )
    assert out["raw_task"] == "fix bug"
    assert out["model"] == "deepseek-v4-flash"


def test_stage_key_preserved():
    # stage_key is a stage identifier, not a credential — it is explicitly
    # allowlisted so the audit log keeps useful context visible.
    assert redact({"stage_key": "01-goal"}) == {"stage_key": "01-goal"}


def test_provider_api_keys_still_redacted():
    # The *_key rule must keep catching provider-style keys not covered by
    # the explicit parts list, so credentials never leak.
    out = redact(
        {
            "openai_key": "sk-aaa",
            "deepseek_key": "sk-bbb",
            "session_api_key": "sk-ccc",
            "stage_key": "02-research",
        }
    )
    assert out["openai_key"] == "[REDACTED]"
    assert out["deepseek_key"] == "[REDACTED]"
    assert out["session_api_key"] == "[REDACTED]"
    assert out["stage_key"] == "02-research"
