"""Outbound HTTP for integrations: timeouts, SSRF protection, secret resolution."""

import ipaddress
import os
import re
import socket
from urllib.parse import urlsplit

import httpx

from app.core.config import get_settings

SECRET_REF_PATTERN = re.compile(r"^INTEGRATION_[A-Z0-9_]{3,60}$")
_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
_transport: httpx.AsyncBaseTransport | None = None


class IntegrationError(Exception):
    """Expected integration failure with a message safe to show to staff."""


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    """Tests inject an httpx.MockTransport here; production uses the network."""
    global _transport
    _transport = transport


def client(**kwargs) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=_TIMEOUT,
        transport=_transport,
        follow_redirects=False,
        headers={"User-Agent": "Eranova-Orbit/1.0"},
        **kwargs,
    )


def resolve_host(host: str) -> list[str]:
    return [info[4][0] for info in socket.getaddrinfo(host, None)]


def ensure_safe_url(url: str) -> str:
    """Reject URLs that could reach internal infrastructure (SSRF).

    Only https is allowed (http also on localhost in local development), and
    the host must resolve to public addresses.
    """
    parts = urlsplit(url)
    local_dev = get_settings().environment == "local"
    if parts.scheme not in ("https", "http") or not parts.hostname:
        raise IntegrationError("Use a full https:// URL.")
    if parts.username or parts.password:
        raise IntegrationError("Credentials must not be embedded in URLs; use a secret reference.")
    if parts.scheme == "http" and not local_dev:
        raise IntegrationError("Only https:// URLs are allowed.")
    try:
        addresses = resolve_host(parts.hostname)
    except OSError as exc:
        raise IntegrationError(f"Could not resolve {parts.hostname}.") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        internal = (
            ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
        )
        if internal and not local_dev:
            raise IntegrationError("URLs that point to internal network addresses are not allowed.")
    return url


def resolve_secret(secret_ref: str | None, *, required: bool) -> str | None:
    """Read a credential from server-side environment configuration by name.

    Only names starting with INTEGRATION_ are readable, so a misconfigured
    connection can never send Orbit's own secrets (e.g. SECRET_KEY) elsewhere.
    """
    if not secret_ref:
        if required:
            raise IntegrationError("This integration needs a secret reference.")
        return None
    if not SECRET_REF_PATTERN.match(secret_ref):
        raise IntegrationError("Secret references must look like INTEGRATION_NAME.")
    value = os.environ.get(secret_ref)
    if not value:
        raise IntegrationError(
            f"The server has no value for {secret_ref}. Add it to the environment."
        )
    return value


def raise_for_status(response: httpx.Response, service: str) -> None:
    if response.status_code in (401, 403):
        raise IntegrationError(f"{service} rejected the credentials ({response.status_code}).")
    if response.status_code == 404:
        raise IntegrationError(f"{service} could not find the configured resource.")
    if response.status_code == 429:
        raise IntegrationError(f"{service} rate limit reached; try again later.")
    if response.status_code >= 400:
        raise IntegrationError(f"{service} returned an error ({response.status_code}).")
