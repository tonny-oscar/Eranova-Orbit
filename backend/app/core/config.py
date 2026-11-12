from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]

_INSECURE_SECRET_MARKERS = ("change-me", "changeme", "local-only", "insecure")


def normalize_database_url(url: str) -> str:
    """Convert provider URLs (e.g. Render's ``postgresql://``) to the asyncpg dialect.

    asyncpg does not understand libpq's ``sslmode`` query parameter, so it is
    translated to the equivalent ``ssl`` parameter.
    """
    parts = urlsplit(url)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql", "postgresql+psycopg", "postgresql+psycopg2"):
        scheme = "postgresql+asyncpg"
    query = [("ssl" if key == "sslmode" else key, value) for key, value in parse_qsl(parts.query)]
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Environment = "local"
    log_level: str = "INFO"

    database_url: str
    db_pool_size: int = 5
    db_max_overflow: int = 5

    secret_key: str = Field(min_length=32)

    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    session_cookie_name: str = "orbit_session"
    session_cookie_secure: bool = False
    session_cookie_domain: str | None = None
    session_idle_minutes: int = Field(default=60, ge=5, le=24 * 60)
    session_absolute_hours: int = Field(default=12, ge=1, le=24 * 30)

    login_window_minutes: int = Field(default=15, ge=1)
    login_max_failures_per_email: int = Field(default=5, ge=1)
    login_max_failures_per_ip: int = Field(default=20, ge=1)

    company_name: str = "Eranova Technologies"
    company_slug: str = "eranova"
    company_timezone: str = "Africa/Nairobi"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("session_cookie_domain", mode="before")
    @classmethod
    def _empty_domain_is_none(cls, value: object) -> object:
        return value or None

    @model_validator(mode="after")
    def _enforce_deployed_safety(self) -> "Settings":
        if self.is_deployed:
            lowered = self.secret_key.lower()
            if any(marker in lowered for marker in _INSECURE_SECRET_MARKERS):
                raise ValueError("SECRET_KEY must be a unique random value in staging/production")
            if not self.session_cookie_secure:
                raise ValueError("SESSION_COOKIE_SECURE must be true in staging/production")
        return self

    @property
    def is_deployed(self) -> bool:
        return self.environment in ("staging", "production")

    @property
    def docs_enabled(self) -> bool:
        return self.environment != "production"

    @property
    def effective_cookie_name(self) -> str:
        # The __Host- prefix makes browsers reject the cookie unless it is Secure,
        # host-only and scoped to "/", which blocks subdomain cookie injection.
        if self.session_cookie_secure and not self.session_cookie_domain:
            return f"__Host-{self.session_cookie_name}"
        return self.session_cookie_name


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
