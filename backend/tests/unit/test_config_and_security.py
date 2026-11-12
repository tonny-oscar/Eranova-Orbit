import pytest
from pydantic import ValidationError

from app.core.config import Settings, normalize_database_url
from app.core.redaction import REDACTED, redact
from app.core.security import (
    csrf_token_matches,
    derive_csrf_token,
    hash_password,
    hash_token,
    verify_password,
)

SECRET = "x" * 40


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgres://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        ("postgresql://u:p@h/db?sslmode=require", "postgresql+asyncpg://u:p@h/db?ssl=require"),
        ("postgresql+asyncpg://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
    ],
)
def test_database_url_normalization(raw, expected):
    assert normalize_database_url(raw) == expected


def _settings(**overrides) -> Settings:
    base = {"database_url": "postgresql://u:p@h/db", "secret_key": SECRET, "_env_file": None}
    return Settings(**(base | overrides))


def test_production_rejects_insecure_cookie():
    with pytest.raises(ValidationError):
        _settings(environment="production", session_cookie_secure=False)


def test_production_rejects_placeholder_secret():
    with pytest.raises(ValidationError):
        _settings(
            environment="production",
            session_cookie_secure=True,
            secret_key="replace-with-a-long-random-value-change-me",
        )


def test_secure_host_only_cookie_uses_host_prefix():
    settings = _settings(environment="production", session_cookie_secure=True)
    assert settings.effective_cookie_name == "__Host-orbit_session"
    assert not settings.docs_enabled


def test_cookie_with_domain_cannot_use_host_prefix():
    settings = _settings(session_cookie_secure=True, session_cookie_domain="eranova.example")
    assert settings.effective_cookie_name == "orbit_session"


def test_cors_origins_parse_from_comma_string():
    settings = _settings(cors_allowed_origins="https://a.example/, https://b.example")
    assert settings.cors_allowed_origins == ["https://a.example", "https://b.example"]


def test_password_hash_roundtrip_and_none_hash():
    hashed = hash_password("a-long-enough-password")
    assert hashed.startswith("$argon2id$")
    assert verify_password("a-long-enough-password", hashed)
    assert not verify_password("wrong-password-value", hashed)
    assert not verify_password("anything", None)


def test_csrf_token_bound_to_session_token():
    token = derive_csrf_token("session-a", SECRET)
    assert csrf_token_matches(token, "session-a", SECRET)
    assert not csrf_token_matches(token, "session-b", SECRET)
    assert not csrf_token_matches(None, "session-a", SECRET)


def test_token_hash_is_deterministic_and_not_plaintext():
    assert hash_token("abc") == hash_token("abc")
    assert "abc" not in hash_token("abc")


def test_redaction_masks_nested_sensitive_keys():
    data = {
        "email": "a@b.c",
        "password": "p",
        "nested": {"api_key": "k", "items": [{"token": "t"}]},
    }
    assert redact(data) == {
        "email": "a@b.c",
        "password": REDACTED,
        "nested": {"api_key": REDACTED, "items": [{"token": REDACTED}]},
    }
