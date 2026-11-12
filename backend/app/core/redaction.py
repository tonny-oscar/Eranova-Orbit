from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"

_SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "private_key",
    "credential",
)


def is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in _SENSITIVE_KEY_FRAGMENTS)


def redact(value: Any, _depth: int = 0) -> Any:
    """Return a copy of ``value`` with sensitive keys masked, recursively."""
    if _depth > 8:
        return REDACTED
    if isinstance(value, Mapping):
        return {
            key: REDACTED if is_sensitive_key(str(key)) else redact(item, _depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact(item, _depth + 1) for item in value]
    return value
