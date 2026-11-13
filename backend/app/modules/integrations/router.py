import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_request_meta, require_permission
from app.core.request_meta import RequestMeta
from app.db.base import utc_now
from app.db.session import get_db
from app.integrations.registry import PROVIDERS
from app.modules.authorization.policy import is_allowed
from app.modules.integrations import service
from app.modules.integrations.models import IntegrationConnection, IntegrationRecord
from app.modules.products import service as product_service
from app.modules.products.models import Product

router = APIRouter(tags=["integrations"])


class ProviderOut(BaseModel):
    provider: str
    label: str
    description: str
    capabilities: list[str]
    config_fields: list[dict[str, Any]]
    secret_required: bool
    secret_help: str
    supports_webhooks: bool


class ConnectionOut(BaseModel):
    id: uuid.UUID
    provider: str
    provider_label: str
    name: str
    product: dict | None
    config: dict[str, Any]
    secret_ref: str | None
    webhook_secret_ref: str | None
    capabilities: list[str]
    status: str
    sync_interval_minutes: int
    last_sync_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    is_stale: bool
    webhook_url: str | None = None
    can_manage: bool = False


class RunOut(BaseModel):
    id: uuid.UUID
    trigger: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    summary: dict[str, Any]
    error: str | None


class RecordOut(BaseModel):
    kind: str
    external_id: str
    data: dict[str, Any]
    observed_at: datetime


def _record(r: IntegrationRecord) -> RecordOut:
    return RecordOut(kind=r.kind, external_id=r.external_id, data=r.data, observed_at=r.observed_at)


async def _products(db: AsyncSession, ids) -> dict:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {p.id: p for p in await db.scalars(select(Product).where(Product.id.in_(ids)))}


def _out(
    c: IntegrationConnection, products: dict, auth: AuthContext, request: Request | None = None
) -> ConnectionOut:
    product = products.get(c.product_id)
    cls = PROVIDERS.get(c.provider)
    webhook_url = None
    if request is not None and cls and cls.supports_webhooks:
        webhook_url = str(request.base_url).rstrip("/") + f"/api/v1/webhooks/{c.provider}/{c.id}"
    return ConnectionOut(
        id=c.id,
        provider=c.provider,
        provider_label=cls.label if cls else c.provider,
        name=c.name,
        product={"id": str(product.id), "name": product.name} if product else None,
        config=c.config,
        secret_ref=c.secret_ref,
        webhook_secret_ref=c.webhook_secret_ref,
        capabilities=c.capabilities,
        status=c.status,
        sync_interval_minutes=c.sync_interval_minutes,
        last_sync_at=c.last_sync_at,
        last_success_at=c.last_success_at,
        last_error=c.last_error,
        is_stale=service.is_stale(c),
        webhook_url=webhook_url,
        can_manage=is_allowed(auth.principal, "integration.manage", service.connection_context(c)),
    )


@router.get("/integrations/providers", response_model=list[ProviderOut])
async def providers(
    _: AuthContext = Depends(require_permission("integration.read")),
) -> list[ProviderOut]:
    return [
        ProviderOut(
            provider=cls.provider,
            label=cls.label,
            description=cls.description,
            capabilities=list(cls.capabilities),
            config_fields=[
                {
                    "name": f.name,
                    "label": f.label,
                    "required": f.required,
                    "help": f.help,
                    "kind": f.kind,
                }
                for f in cls.config_fields
            ],
            secret_required=cls.secret_required,
            secret_help=cls.secret_help,
            supports_webhooks=cls.supports_webhooks,
        )
        for cls in PROVIDERS.values()
    ]


@router.get("/integrations", response_model=list[ConnectionOut])
async def list_integrations(
    product_id: uuid.UUID | None = None,
    auth: AuthContext = Depends(require_permission("integration.read")),
    db: AsyncSession = Depends(get_db),
) -> list[ConnectionOut]:
    rows = await service.list_connections(db, auth.principal, product_id)
    products = await _products(db, {c.product_id for c in rows})
    return [_out(c, products, auth) for c in rows]


@router.post("/integrations", response_model=ConnectionOut, status_code=201)
async def create_integration(
    payload: service.ConnectionIn,
    request: Request,
    auth: AuthContext = Depends(require_permission("integration.manage")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ConnectionOut:
    c = await service.create_connection(db, auth.user, auth.principal, payload, meta)
    return _out(c, await _products(db, {c.product_id}), auth, request)


@router.get("/integrations/{connection_id}", response_model=ConnectionOut)
async def get_integration(
    connection_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(require_permission("integration.read")),
    db: AsyncSession = Depends(get_db),
) -> ConnectionOut:
    c = await service.get_connection(db, auth.principal, connection_id)
    return _out(c, await _products(db, {c.product_id}), auth, request)


@router.patch("/integrations/{connection_id}", response_model=ConnectionOut)
async def update_integration(
    connection_id: uuid.UUID,
    payload: service.ConnectionPatch,
    request: Request,
    auth: AuthContext = Depends(require_permission("integration.manage")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ConnectionOut:
    c = await service.update_connection(db, auth.user, auth.principal, connection_id, payload, meta)
    return _out(c, await _products(db, {c.product_id}), auth, request)


@router.delete("/integrations/{connection_id}", status_code=204)
async def delete_integration(
    connection_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("integration.delete")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    await service.delete_connection(db, auth.user, auth.principal, connection_id, meta)
    return Response(status_code=204)


@router.post("/integrations/{connection_id}/test")
async def test_integration(
    connection_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("integration.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> dict:
    result = await service.test_connection(db, auth.user, auth.principal, connection_id, meta)
    return {"ok": result.ok, "message": result.message, "details": result.details}


@router.post("/integrations/{connection_id}/sync", response_model=RunOut)
async def sync_integration(
    connection_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("integration.update")),
    db: AsyncSession = Depends(get_db),
) -> RunOut:
    run = await service.sync_connection(db, auth.user, auth.principal, connection_id)
    return RunOut.model_validate(run, from_attributes=True)


@router.get("/integrations/{connection_id}/runs", response_model=list[RunOut])
async def integration_runs(
    connection_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("integration.read")),
    db: AsyncSession = Depends(get_db),
) -> list[RunOut]:
    c = await service.get_connection(db, auth.principal, connection_id)
    return [
        RunOut.model_validate(r, from_attributes=True) for r in await service.runs_for(db, c.id)
    ]


@router.get("/integrations/{connection_id}/records", response_model=list[RecordOut])
async def integration_records(
    connection_id: uuid.UUID,
    kind: str = Query(..., max_length=40),
    auth: AuthContext = Depends(require_permission("integration.read")),
    db: AsyncSession = Depends(get_db),
) -> list[RecordOut]:
    c = await service.get_connection(db, auth.principal, connection_id)
    return [_record(r) for r in await service.records_for(db, [c.id], kind)]


@router.post("/webhooks/{provider}/{connection_id}")
async def receive_webhook(
    provider: str, connection_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
) -> dict:
    body = await request.body()
    if len(body) > 1_000_000:
        return Response(status_code=413)
    headers = {k.lower(): v for k, v in request.headers.items()}
    return {"status": await service.handle_webhook(db, provider, connection_id, headers, body)}


# --- Product operations, analytics and monitoring ------------------------------------


async def _connections_by_product(
    db: AsyncSession, company_id, product_ids
) -> dict[uuid.UUID, list]:
    rows = await db.scalars(
        select(IntegrationConnection).where(
            IntegrationConnection.company_id == company_id,
            IntegrationConnection.product_id.in_(product_ids),
        )
    )
    grouped = defaultdict(list)
    for c in rows:
        grouped[c.product_id].append(c)
    return grouped


def _freshness(connections: list[IntegrationConnection], provider: str) -> dict | None:
    matching = [c for c in connections if c.provider == provider]
    if not matching:
        return None
    latest = max((c.last_success_at for c in matching if c.last_success_at), default=None)
    return {
        "source": matching[0].name,
        "last_success_at": latest,
        "stale": any(service.is_stale(c) for c in matching),
    }


@router.get("/products/{product_id}/operations")
async def product_operations(
    product_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("product.read")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    product = await product_service.get_product_for(db, auth.principal, product_id, "product.read")
    connections = (await _connections_by_product(db, auth.user.company_id, [product.id])).get(
        product.id, []
    )
    ids = [c.id for c in connections]
    since = (utc_now() - timedelta(days=28)).strftime("%Y%m%d")
    traffic = [
        r for r in await service.records_for(db, ids, "traffic_daily", 60) if r.external_id >= since
    ]
    uptime = await service.records_for(db, ids, "uptime_check", 1)
    metrics = await service.records_for(db, ids, "product_metrics", 1)
    return {
        "integrations": [
            {
                "id": str(c.id),
                "name": c.name,
                "provider": c.provider,
                "status": c.status,
                "last_success_at": c.last_success_at,
                "last_error": c.last_error,
                "stale": service.is_stale(c),
            }
            for c in connections
        ],
        "deployments": [
            _record(r).model_dump() for r in await service.records_for(db, ids, "deployment", 5)
        ],
        "pull_requests": [
            _record(r).model_dump() for r in await service.records_for(db, ids, "pull_request", 10)
        ],
        "uptime": _record(uptime[0]).model_dump() if uptime else None,
        "product_metrics": _record(metrics[0]).model_dump() if metrics else None,
        "traffic": {
            "days": len(traffic),
            "totals": {
                key: sum(r.data.get(key, 0) for r in traffic)
                for key in ("activeUsers", "sessions", "screenPageViews", "conversions")
            },
            "series": sorted(
                (
                    {
                        "date": r.data.get("date"),
                        **{k: r.data.get(k) for k in ("activeUsers", "sessions")},
                    }
                    for r in traffic
                ),
                key=lambda x: x["date"] or "",
            ),
        }
        if traffic
        else None,
        "freshness": {
            p: _freshness(connections, p)
            for p in ("ga4", "http_monitor", "vercel", "github", "product_api")
        },
    }


@router.get("/analytics/overview")
async def analytics_overview(
    auth: AuthContext = Depends(require_permission("product.read")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Marketing analytics per product (website traffic and product-reported usage)."""
    page = await product_service.list_products(
        db, auth.principal, q=None, status=None, limit=100, offset=0
    )
    grouped = await _connections_by_product(db, auth.user.company_id, [p.id for p in page.items])
    since = (utc_now() - timedelta(days=28)).strftime("%Y%m%d")
    out = []
    for product in page.items:
        connections = grouped.get(product.id, [])
        ids = [c.id for c in connections]
        traffic = [
            r
            for r in await service.records_for(db, ids, "traffic_daily", 60)
            if r.external_id >= since
        ]
        metrics = await service.records_for(db, ids, "product_metrics", 1)
        out.append(
            {
                "product": {"id": str(product.id), "name": product.name},
                "traffic": {
                    key: sum(r.data.get(key, 0) for r in traffic)
                    for key in ("activeUsers", "sessions", "screenPageViews", "conversions")
                }
                if traffic
                else None,
                "traffic_freshness": _freshness(connections, "ga4"),
                "product_metrics": metrics[0].data.get("metrics") if metrics else None,
                "product_metrics_freshness": _freshness(connections, "product_api"),
            }
        )
    return out


@router.get("/monitoring/overview")
async def monitoring_overview(
    auth: AuthContext = Depends(require_permission("integration.read")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Technical monitoring, kept separate from marketing analytics."""
    connections = await service.list_connections(db, auth.principal, None)
    products = await _products(db, {c.product_id for c in connections})
    monitors, deployments, health = [], [], []
    for c in connections:
        product = products.get(c.product_id)
        label = {"id": str(product.id), "name": product.name} if product else None
        health.append(
            {
                "id": str(c.id),
                "name": c.name,
                "provider": c.provider,
                "product": label,
                "status": c.status,
                "last_success_at": c.last_success_at,
                "last_error": c.last_error,
                "stale": service.is_stale(c),
            }
        )
        if c.provider == "http_monitor":
            checks = await service.records_for(db, [c.id], "uptime_check", 48)
            up = [r.data.get("up") for r in checks]
            monitors.append(
                {
                    "id": str(c.id),
                    "name": c.name,
                    "product": label,
                    "url": c.config.get("url"),
                    "latest": _record(checks[0]).model_dump() if checks else None,
                    "uptime_percent": round(100 * sum(1 for u in up if u) / len(up), 1)
                    if up
                    else None,
                    "checks": len(up),
                }
            )
        if c.provider == "vercel":
            latest = await service.records_for(db, [c.id], "deployment", 1)
            deployments.append(
                {
                    "name": c.name,
                    "product": label,
                    "latest": _record(latest[0]).model_dump() if latest else None,
                }
            )
    return {"integrations": health, "monitors": monitors, "deployments": deployments}
