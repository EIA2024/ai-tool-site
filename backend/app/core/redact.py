"""Secret redaction helpers for audit logs and diagnostics.

A live credential can reach the backend through ordinary request fields
(e.g. a user-supplied DeepSeek key in ``session_api_key``). First-principles
rule: credentials must never be persisted or echoed, so any value nested
under a sensitive-looking key is replaced before it is serialized into the
audit table or logged.
"""

from typing import Any

_REDACTED = "[REDACTED]"

# Substring matches on lowercase key names. "api_key" and "session_api_key"
# are caught by both the explicit list and the "_key" suffix rule; "token",
# "secret", "authorization", etc. cover other credential shapes.
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "token",
    "password",
    "secret",
    "authorization",
    "credential",
)


def _is_sensitive_key(key: str) -> bool:
    lowered = str(key).lower()
    if lowered == "key" or lowered.endswith("_key"):
        return True
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def redact(value: Any) -> Any:
    """Recursively replace values stored under sensitive keys with a placeholder.

    Plain strings and numbers are returned untouched; dicts and lists are
    walked depth-first. ``stage_key`` is redacted too (harmless — it is only
    a stage identifier), keeping the rule simple and predictable.
    """
    if isinstance(value, dict):
        return {
            k: (_REDACTED if _is_sensitive_key(k) else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value
