import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.modules.audit.models import AuditLog
from tests.conftest import login


async def test_audit_log_requires_permission(client, make_user):
    await make_user("dev@eranova.co.ke", role="developer")
    await login(client, "dev@eranova.co.ke")
    assert (await client.get("/api/v1/audit-logs")).status_code == 403


async def test_denied_sensitive_access_is_audited(client, make_user, db):
    user = await make_user("dev@eranova.co.ke", role="developer")
    await login(client, "dev@eranova.co.ke")
    await client.get("/api/v1/audit-logs")
    event = await db.scalar(
        select(AuditLog).where(AuditLog.action == "authz.denied", AuditLog.actor_user_id == user.id)
    )
    assert event is not None
    assert event.details["permission"] == "audit_log.read"


async def test_auditor_reads_company_audit_log(client, make_user):
    await make_user("auditor@eranova.co.ke", role="auditor")
    await login(client, "auditor@eranova.co.ke")
    response = await client.get("/api/v1/audit-logs", params={"action": "auth.login.succeeded"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert body["items"][0]["action"] == "auth.login.succeeded"
    assert body["items"][0]["correlation_id"]


async def test_audit_log_scoped_grant_is_not_enough(client, make_user, db):
    import uuid

    await make_user(
        "scoped@eranova.co.ke", role="auditor", scope_type="project", scope_id=uuid.uuid4()
    )
    await login(client, "scoped@eranova.co.ke")
    assert (await client.get("/api/v1/audit-logs")).status_code == 403


@pytest.mark.parametrize(
    "statement",
    ["UPDATE audit_logs SET action = 'tampered'", "DELETE FROM audit_logs"],
)
async def test_audit_log_is_append_only(db, company, statement):
    from app.core.request_meta import SYSTEM_META
    from app.modules.audit.models import AuditOutcome
    from app.modules.audit.service import record_event

    await record_event(
        db,
        action="test.event",
        outcome=AuditOutcome.SUCCESS,
        meta=SYSTEM_META,
        company_id=company.id,
    )
    with pytest.raises(DBAPIError, match="append-only"):
        async with db.begin_nested():
            await db.execute(text(statement))
