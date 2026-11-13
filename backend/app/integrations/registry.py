from app.integrations.base import Adapter
from app.integrations.ga4 import GA4Adapter
from app.integrations.github import GitHubAdapter
from app.integrations.http import IntegrationError
from app.integrations.http_monitor import HttpMonitorAdapter
from app.integrations.product_api import ProductApiAdapter
from app.integrations.vercel import VercelAdapter

PROVIDERS: dict[str, type[Adapter]] = {
    cls.provider: cls
    for cls in (ProductApiAdapter, GitHubAdapter, VercelAdapter, GA4Adapter, HttpMonitorAdapter)
}


def adapter_class(provider: str) -> type[Adapter]:
    try:
        return PROVIDERS[provider]
    except KeyError as exc:
        raise IntegrationError(f"Unknown integration provider '{provider}'.") from exc
