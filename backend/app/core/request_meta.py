from dataclasses import dataclass

from fastapi import Request

from app.core.context import get_correlation_id


@dataclass(frozen=True)
class RequestMeta:
    ip_address: str | None
    user_agent: str | None
    correlation_id: str | None


def request_meta(request: Request) -> RequestMeta:
    # request.client reflects X-Forwarded-For only when uvicorn runs with
    # --proxy-headers behind a trusted proxy (configured for Render).
    user_agent = request.headers.get("user-agent")
    return RequestMeta(
        ip_address=request.client.host if request.client else None,
        user_agent=user_agent[:255] if user_agent else None,
        correlation_id=get_correlation_id(),
    )


SYSTEM_META = RequestMeta(ip_address=None, user_agent="orbit-cli", correlation_id=None)
