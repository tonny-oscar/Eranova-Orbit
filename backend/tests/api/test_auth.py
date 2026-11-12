from datetime import timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.modules.audit.models import AuditLog
from app.modules.identity.models import UserSession, UserStatus
from app.modules.identity.service import utcnow
from tests.conftest import DEFAULT_PASSWORD, login

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"
LOGOUT = "/api/v1/auth/logout"
CHANGE_PASSWORD = "/api/v1/auth/change-password"


async def test_login_sets_httponly_cookie_and_returns_profile(client, make_user):
    await make_user("ada@eranova.co.ke", role="executive", full_name="Ada")
    response = await client.post(
        LOGIN, json={"email": " ADA@eranova.co.ke ", "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "ada@eranova.co.ke"
    assert body["company"]["slug"] == "eranova"
    assert "product.read" in body["permissions"]
    assert "role.manage" not in body["permissions"]
    assert body["roles"][0]["role_slug"] == "executive"
    assert body["csrf_token"]
    cookie_header = response.headers["set-cookie"].lower()
    assert "orbit_session=" in cookie_header
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header


async def test_session_token_is_stored_hashed(client, make_user, db):
    await make_user("hash@eranova.co.ke")
    await login(client, "hash@eranova.co.ke")
    token = client.cookies.get("orbit_session")
    stored = await db.scalar(select(UserSession.token_hash))
    assert token and stored and token != stored


async def test_wrong_password_and_unknown_email_get_identical_errors(client, make_user):
    await make_user("bob@eranova.co.ke")
    wrong = await client.post(
        LOGIN, json={"email": "bob@eranova.co.ke", "password": "nope-nope-nope"}
    )
    unknown = await client.post(
        LOGIN, json={"email": "ghost@eranova.co.ke", "password": "nope-nope-nope"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]
    assert "set-cookie" not in wrong.headers


async def test_failed_login_is_audited_without_password(client, make_user, db):
    await make_user("audit@eranova.co.ke")
    await client.post(LOGIN, json={"email": "audit@eranova.co.ke", "password": "bad-password-123"})
    event = await db.scalar(select(AuditLog).where(AuditLog.action == "auth.login.failed"))
    assert event is not None
    assert event.details["reason"] == "invalid_password"
    assert "bad-password-123" not in str(event.details)


async def test_disabled_user_cannot_login(client, make_user, db):
    user = await make_user("gone@eranova.co.ke")
    user.status = UserStatus.DISABLED
    await db.commit()
    response = await client.post(
        LOGIN, json={"email": "gone@eranova.co.ke", "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 401


async def test_repeated_failures_are_throttled(client, make_user):
    await make_user("slow@eranova.co.ke")
    for _ in range(5):
        r = await client.post(
            LOGIN, json={"email": "slow@eranova.co.ke", "password": "wrong-wrong-1"}
        )
        assert r.status_code == 401
    throttled = await client.post(
        LOGIN, json={"email": "slow@eranova.co.ke", "password": DEFAULT_PASSWORD}
    )
    assert throttled.status_code == 429
    assert "Retry-After" in throttled.headers


async def test_me_requires_authentication(client):
    response = await client.get(ME)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


async def test_me_returns_current_user(client, make_user):
    await make_user("me@eranova.co.ke")
    await login(client, "me@eranova.co.ke")
    response = await client.get(ME)
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "me@eranova.co.ke"
    assert response.json()["permissions"] == []


async def test_unsafe_request_requires_csrf_token(client, make_user):
    await make_user("csrf@eranova.co.ke")
    csrf = await login(client, "csrf@eranova.co.ke")

    missing = await client.post(LOGOUT)
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "csrf_failed"

    forged = await client.post(LOGOUT, headers={"X-CSRF-Token": "0" * 64})
    assert forged.status_code == 403

    ok = await client.post(LOGOUT, headers={"X-CSRF-Token": csrf})
    assert ok.status_code == 204


async def test_logout_revokes_session_server_side(client, make_user):
    await make_user("out@eranova.co.ke")
    csrf = await login(client, "out@eranova.co.ke")
    token = client.cookies.get("orbit_session")

    await client.post(LOGOUT, headers={"X-CSRF-Token": csrf})

    # Replaying the old cookie must not work even if the browser kept it.
    client.cookies.set("orbit_session", token)
    assert (await client.get(ME)).status_code == 401


async def test_idle_session_expires(client, make_user, db):
    await make_user("idle@eranova.co.ke")
    await login(client, "idle@eranova.co.ke")
    session_row = await db.scalar(select(UserSession))
    session_row.last_seen_at = utcnow() - timedelta(hours=2)
    await db.commit()
    assert (await client.get(ME)).status_code == 401


async def test_absolute_session_expiry(client, make_user, db):
    await make_user("abs@eranova.co.ke")
    await login(client, "abs@eranova.co.ke")
    session_row = await db.scalar(select(UserSession))
    session_row.expires_at = utcnow() - timedelta(seconds=1)
    await db.commit()
    assert (await client.get(ME)).status_code == 401


async def test_change_password_revokes_other_sessions(app, client, make_user):
    await make_user("pw@eranova.co.ke")
    csrf = await login(client, "pw@eranova.co.ke")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as other:
        await login(other, "pw@eranova.co.ke")

        response = await client.post(
            CHANGE_PASSWORD,
            json={"current_password": DEFAULT_PASSWORD, "new_password": "a-brand-new-passphrase"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 204
        assert (await client.get(ME)).status_code == 200
        assert (await other.get(ME)).status_code == 401

    relogin = await client.post(
        LOGIN, json={"email": "pw@eranova.co.ke", "password": "a-brand-new-passphrase"}
    )
    assert relogin.status_code == 200


async def test_change_password_enforces_policy(client, make_user):
    await make_user("weak@eranova.co.ke")
    csrf = await login(client, "weak@eranova.co.ke")
    response = await client.post(
        CHANGE_PASSWORD,
        json={"current_password": DEFAULT_PASSWORD, "new_password": "short"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "weak_password"


async def test_change_password_rejects_wrong_current_password(client, make_user):
    await make_user("cur@eranova.co.ke")
    csrf = await login(client, "cur@eranova.co.ke")
    response = await client.post(
        CHANGE_PASSWORD,
        json={"current_password": "not-the-password", "new_password": "a-brand-new-passphrase"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_current_password"


async def test_operator_password_reset_signs_out_everywhere(client, make_user, db, company):
    from app.core.request_meta import SYSTEM_META
    from app.modules.identity.service import reset_password_as_system

    await make_user("reset@eranova.co.ke")
    await login(client, "reset@eranova.co.ke")

    await reset_password_as_system(
        db,
        company=company,
        email="reset@eranova.co.ke",
        new_password="operator-chosen-passphrase",
        meta=SYSTEM_META,
    )

    assert (await client.get(ME)).status_code == 401
    relogin = await client.post(
        LOGIN, json={"email": "reset@eranova.co.ke", "password": "operator-chosen-passphrase"}
    )
    assert relogin.status_code == 200
    event = await db.scalar(select(AuditLog).where(AuditLog.action == "auth.password.reset"))
    assert event is not None and event.actor_type == "system"


async def test_validation_errors_do_not_echo_input(client):
    response = await client.post(LOGIN, json={"email": "x", "password": ""})
    assert response.status_code == 422
    assert "input" not in str(response.json()["error"]["details"])
