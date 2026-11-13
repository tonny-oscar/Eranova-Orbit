"""Common adapter contract (architecture §5.2).

Not every adapter supports every capability; each declares what it supports
and the registry stores that per connection.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar


@dataclass
class Record:
    """A normalised external fact Orbit keeps a minimal copy of."""

    kind: str
    external_id: str
    data: dict[str, Any]
    observed_at: datetime | None = None


@dataclass
class HealthResult:
    ok: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncResult:
    records: list[Record]
    summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookResult:
    event_type: str
    delivery_id: str
    summary: dict[str, Any]
    records: list[Record] = field(default_factory=list)
    # (task external_ref, url, title, kind) evidence to attach to matching tasks
    task_evidence: list[tuple[str, str, str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class ConfigField:
    name: str
    label: str
    required: bool = True
    help: str = ""
    kind: str = "text"  # text | url | number


class Adapter:
    provider: ClassVar[str]
    label: ClassVar[str]
    description: ClassVar[str]
    capabilities: ClassVar[tuple[str, ...]]
    config_fields: ClassVar[tuple[ConfigField, ...]]
    secret_required: ClassVar[bool] = False
    secret_help: ClassVar[str] = ""
    supports_webhooks: ClassVar[bool] = False

    def __init__(
        self, config: dict[str, Any], secret: str | None, webhook_secret: str | None = None
    ):
        self.config = config
        self.secret = secret
        self.webhook_secret = webhook_secret

    @classmethod
    def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Return the cleaned config or raise IntegrationError."""
        return config

    async def health_check(self) -> HealthResult:
        raise NotImplementedError

    async def sync(self) -> SyncResult:
        raise NotImplementedError

    def verify_webhook(self, headers: dict[str, str], body: bytes) -> bool:
        return False

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> WebhookResult:
        raise NotImplementedError
