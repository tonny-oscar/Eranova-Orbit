import logging
import uuid
from datetime import timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, delete, false, func, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.request_meta import SYSTEM_META
from app.db.base import utc_now
from app.integrations.base import Adapter, HealthResult, Record
from app.integrations.http import SECRET_REF_PATTERN, IntegrationError, resolve_secret
from app.integrations.registry import PROVIDERS, adapter_class
from app.modules.audit.models import ActorType, AuditOutcome
from app.modules.audit.service import record_event
from app.modules.authorization.policy import Principal, ResourceContext, is_allowed, scope_filter
from app.modules.identity.models import User
from app.modules.integrations.models import (
    IntegrationConnection,
    IntegrationRecord,
    SyncRun,
    WebhookEvent,
)
from app.modules.products.models import Product
from app.modules.work.models import Task, TaskEvent, TaskLink

logger = logging.getLogger(__name__)


class ConnectionIn(BaseModel):
    provider: str = Field(max_length=30)
    name: str = Field(min_length=2, max_length=120)
    product_id: uuid.UUID | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    secret_ref: str | None = Field(default=None, max_length=80)
    webhook_secret_ref: str | None = Field(default=None, max_length=80)
    sync_interval_minutes: int = Field(default=60, ge=5, le=24 * 60)


class ConnectionPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    config: dict[str, Any] | None = None
    secret_ref: str | None = Field(default=None, max_length=80)
    webhook_secret_ref: str | None = Field(default=None, max_length=80)
    sync_interval_minutes: int | None = Field(default=None, ge=5, le=24 * 60)
    status: str | None = Field(default=None, pattern="^(active|paused)$")


def connection_context(connection: IntegrationConnection) -> ResourceContext:
    return ResourceContext(
        company_id=connection.company_id,
        product_ids=frozenset({connection.product_id}) if connection.product_id else frozenset(),
    )


def scope_condition(principal: Principal) -> ColumnElement[bool]:
    scope = scope_filter(principal, "integration.read")
    if scope.company_wide:
        return true()
    if scope.product_ids:
        return IntegrationConnection.product_id.in_(scope.product_ids)
    return false()


def _check_secret_ref(value: str | None, *, label: str) -> str | None:
    if value in (None, ""):
        return None
    if not SECRET_REF_PATTERN.match(value):
        raise AppError(
            f"{label} must look like INTEGRATION_NAME (letters, digits, underscores).",
            code="invalid_secret_ref",
        )
    return value


def _validate_config(provider: str, config: dict) -> dict:
    try:
        return adapter_class(provider).validate_config(config)
    except IntegrationError as exc:
        raise AppError(str(exc), code="invalid_integration_config") from exc


async def get_connection(
    session: AsyncSession,
    principal: Principal,
    connection_id: uuid.UUID,
    permission: str = "integration.read",
) -> IntegrationConnection:
    connection = await session.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.id == connection_id,
            IntegrationConnection.company_id == principal.company_id,
        )
    )
    if connection is None or not is_allowed(
        principal, "integration.read", connection_context(connection)
    ):
        raise NotFoundError("Integration not found.")
    if permission != "integration.read" and not is_allowed(
        principal, permission, connection_context(connection)
    ):
        raise PermissionDeniedError("You cannot change this integration.")
    return connection


async def list_connections(
    session: AsyncSession, principal: Principal, product_id: uuid.UUID | None
):
    conditions = [
        IntegrationConnection.company_id == principal.company_id,
        scope_condition(principal),
    ]
    if product_id:
        conditions.append(IntegrationConnection.product_id == product_id)
    return list(
        await session.scalars(
            select(IntegrationConnection).where(*conditions).order_by(IntegrationConnection.name)
        )
    )


async def _audit(
    session, actor: User | None, action: str, connection: IntegrationConnection, meta, details=None
):
    await record_event(
        session,
        action=action,
        outcome=AuditOutcome.SUCCESS,
        actor_type=ActorType.USER if actor else ActorType.SYSTEM,
        actor_user_id=actor.id if actor else None,
        company_id=connection.company_id,
        resource_type="integration",
        resource_id=connection.id,
        meta=meta,
        details=details or {},
    )


async def create_connection(
    session, actor: User, principal: Principal, payload: ConnectionIn, meta
) -> IntegrationConnection:
    context = ResourceContext(
        company_id=actor.company_id,
        product_ids=frozenset({payload.product_id}) if payload.product_id else frozenset(),
    )
    if not is_allowed(principal, "integration.manage", context):
        raise PermissionDeniedError("You cannot add integrations here.")
    cls = adapter_class(payload.provider) if payload.provider in PROVIDERS else None
    if cls is None:
        raise AppError("Unknown integration provider.", code="unknown_provider")
    if payload.product_id and not await session.scalar(
        select(Product.id).where(
            Product.id == payload.product_id, Product.company_id == actor.company_id
        )
    ):
        raise AppError("Product not found.", code="invalid_product")
    if await session.scalar(
        select(IntegrationConnection.id).where(
            IntegrationConnection.company_id == actor.company_id,
            func.lower(IntegrationConnection.name) == payload.name.strip().lower(),
        )
    ):
        raise ConflictError(
            "An integration with this name already exists.", code="integration_name_taken"
        )
    secret_ref = _check_secret_ref(payload.secret_ref, label="Secret reference")
    if cls.secret_required and not secret_ref:
        raise AppError("This provider needs a secret reference.", code="secret_required")
    connection = IntegrationConnection(
        company_id=actor.company_id,
        product_id=payload.product_id,
        provider=payload.provider,
        name=payload.name.strip(),
        config=_validate_config(payload.provider, payload.config),
        secret_ref=secret_ref,
        webhook_secret_ref=_check_secret_ref(
            payload.webhook_secret_ref, label="Webhook secret reference"
        ),
        capabilities=list(cls.capabilities),
        sync_interval_minutes=payload.sync_interval_minutes,
        created_by_user_id=actor.id,
    )
    session.add(connection)
    await session.flush()
    await _audit(
        session,
        actor,
        "integration.create",
        connection,
        meta,
        {"provider": connection.provider, "name": connection.name},
    )
    await session.commit()
    return connection


async def update_connection(
    session, actor, principal, connection_id, payload: ConnectionPatch, meta
) -> IntegrationConnection:
    connection = await get_connection(session, principal, connection_id, "integration.manage")
    changes = payload.model_dump(exclude_unset=True)
    if "config" in changes and changes["config"] is not None:
        connection.config = _validate_config(connection.provider, changes["config"])
    if "secret_ref" in changes:
        connection.secret_ref = _check_secret_ref(changes["secret_ref"], label="Secret reference")
        if adapter_class(connection.provider).secret_required and not connection.secret_ref:
            raise AppError("This provider needs a secret reference.", code="secret_required")
    if "webhook_secret_ref" in changes:
        connection.webhook_secret_ref = _check_secret_ref(
            changes["webhook_secret_ref"], label="Webhook secret reference"
        )
    for field in ("name", "sync_interval_minutes", "status"):
        if changes.get(field) is not None:
            setattr(
                connection, field, changes[field].strip() if field == "name" else changes[field]
            )
    await _audit(
        session, actor, "integration.update", connection, meta, {"fields": sorted(changes)}
    )
    await session.commit()
    await session.refresh(connection)
    return connection


async def delete_connection(session, actor, principal, connection_id, meta) -> None:
    connection = await get_connection(session, principal, connection_id, "integration.delete")
    await _audit(session, actor, "integration.delete", connection, meta, {"name": connection.name})
    await session.delete(connection)
    await session.commit()


def build_adapter(
    connection: IntegrationConnection, *, need_webhook_secret: bool = False
) -> Adapter:
    cls = adapter_class(connection.provider)
    secret = resolve_secret(connection.secret_ref, required=cls.secret_required)
    webhook_secret = (
        resolve_secret(connection.webhook_secret_ref, required=True)
        if need_webhook_secret
        else None
    )
    return cls(connection.config, secret, webhook_secret)


async def upsert_records(
    session: AsyncSession, connection_id: uuid.UUID, records: list[Record]
) -> None:
    for record in records:
        statement = insert(IntegrationRecord).values(
            id=uuid.uuid4(),
            connection_id=connection_id,
            kind=record.kind,
            external_id=record.external_id[:200],
            data=record.data,
            observed_at=record.observed_at or utc_now(),
        )
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=["connection_id", "kind", "external_id"],
                set_={
                    "data": statement.excluded.data,
                    "observed_at": statement.excluded.observed_at,
                },
            )
        )


async def test_connection(session, actor, principal, connection_id, meta) -> HealthResult:
    connection = await get_connection(session, principal, connection_id, "integration.update")
    try:
        result = await build_adapter(connection).health_check()
    except IntegrationError as exc:
        result = HealthResult(False, str(exc))
    except Exception:
        logger.exception(
            "Integration health check crashed", extra={"connection_id": str(connection.id)}
        )
        result = HealthResult(False, "Unexpected error while contacting the service.")
    connection.last_error = None if result.ok else result.message[:500]
    if connection.status != "paused":
        connection.status = "active" if result.ok else "error"
    await _audit(session, actor, "integration.test", connection, meta, {"ok": result.ok})
    await session.commit()
    return result


async def run_sync(
    session: AsyncSession,
    connection: IntegrationConnection,
    *,
    trigger: str,
    actor: User | None = None,
) -> SyncRun:
    run = SyncRun(connection_id=connection.id, trigger=trigger)
    session.add(run)
    await session.flush()
    connection.last_sync_at = utc_now()
    try:
        result = await build_adapter(connection).sync()
        await upsert_records(session, connection.id, result.records)
        run.status, run.summary = "success", result.summary
        connection.last_success_at = utc_now()
        connection.last_error = None
        if connection.status == "error":
            connection.status = "active"
    except IntegrationError as exc:
        run.status, run.error = "failed", str(exc)[:500]
        connection.last_error, connection.status = run.error, "error"
    except Exception:
        logger.exception("Integration sync crashed", extra={"connection_id": str(connection.id)})
        run.status, run.error = "failed", "Unexpected error during sync."
        connection.last_error, connection.status = run.error, "error"
    run.finished_at = utc_now()
    await _audit(
        session,
        actor,
        "integration.sync",
        connection,
        SYSTEM_META,
        {"status": run.status, "trigger": trigger},
    )
    await session.commit()
    return run


async def sync_connection(session, actor, principal, connection_id) -> SyncRun:
    connection = await get_connection(session, principal, connection_id, "integration.update")
    if connection.status == "paused":
        raise AppError("Resume the integration before syncing.", code="integration_paused")
    return await run_sync(session, connection, trigger="manual", actor=actor)


async def due_connections(session: AsyncSession) -> list[IntegrationConnection]:
    now = utc_now()
    connections = await session.scalars(
        select(IntegrationConnection).where(IntegrationConnection.status != "paused")
    )
    return [
        c
        for c in connections
        if c.last_sync_at is None
        or c.last_sync_at + timedelta(minutes=c.sync_interval_minutes) <= now
    ]


async def handle_webhook(
    session: AsyncSession, provider: str, connection_id: uuid.UUID, headers: dict, body: bytes
) -> str:
    """Verify, de-duplicate and process an inbound webhook. Returns a short status."""
    connection = await session.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.id == connection_id, IntegrationConnection.provider == provider
        )
    )
    if connection is None or not adapter_class(provider).supports_webhooks:
        raise NotFoundError("Not found.")
    try:
        adapter = build_adapter(connection, need_webhook_secret=True)
    except IntegrationError as exc:
        raise PermissionDeniedError(
            "Webhook signing is not configured.", code="webhook_not_configured"
        ) from exc
    if not adapter.verify_webhook(headers, body):
        await record_event(
            session,
            action="integration.webhook.rejected",
            outcome=AuditOutcome.DENIED,
            actor_type=ActorType.ANONYMOUS,
            company_id=connection.company_id,
            resource_type="integration",
            resource_id=connection.id,
            meta=SYSTEM_META,
            details={"reason": "invalid_signature"},
        )
        await session.commit()
        raise PermissionDeniedError("Invalid webhook signature.", code="invalid_signature")
    result = adapter.parse_webhook(headers, body)
    if not result.delivery_id:
        raise AppError("Missing delivery identifier.", code="missing_delivery_id")
    if await session.scalar(
        select(WebhookEvent.id).where(
            WebhookEvent.connection_id == connection.id,
            WebhookEvent.delivery_id == result.delivery_id,
        )
    ):
        return "duplicate"
    session.add(
        WebhookEvent(
            connection_id=connection.id,
            delivery_id=result.delivery_id[:120],
            event_type=result.event_type,
            summary=result.summary,
        )
    )
    await upsert_records(session, connection.id, result.records)
    for external_ref, _url, title, _kind in result.task_evidence:
        tasks = await session.scalars(
            select(Task)
            .join(TaskLink, TaskLink.task_id == Task.id)
            .where(Task.company_id == connection.company_id, TaskLink.external_ref == external_ref)
        )
        for task in tasks:
            # Evidence only: activity on a linked PR never changes task status.
            session.add(TaskEvent(task_id=task.id, kind="evidence", to_value=title[:200]))
    connection.last_success_at = utc_now()
    await session.commit()
    return "processed"


async def records_for(
    session: AsyncSession, connection_ids: list[uuid.UUID], kind: str, limit: int = 50
):
    if not connection_ids:
        return []
    return list(
        await session.scalars(
            select(IntegrationRecord)
            .where(
                IntegrationRecord.connection_id.in_(connection_ids), IntegrationRecord.kind == kind
            )
            .order_by(IntegrationRecord.observed_at.desc())
            .limit(limit)
        )
    )


async def purge_old_checks(session: AsyncSession, days: int = 14) -> int:
    result = await session.execute(
        delete(IntegrationRecord).where(
            IntegrationRecord.kind == "uptime_check",
            IntegrationRecord.observed_at < utc_now() - timedelta(days=days),
        )
    )
    await session.commit()
    return result.rowcount or 0


def is_stale(connection: IntegrationConnection) -> bool:
    if connection.last_success_at is None:
        return True
    return connection.last_success_at < utc_now() - timedelta(
        minutes=connection.sync_interval_minutes * 3
    )


async def runs_for(
    session: AsyncSession, connection_id: uuid.UUID, limit: int = 20
) -> list[SyncRun]:
    return list(
        await session.scalars(
            select(SyncRun)
            .where(SyncRun.connection_id == connection_id)
            .order_by(SyncRun.started_at.desc())
            .limit(limit)
        )
    )
