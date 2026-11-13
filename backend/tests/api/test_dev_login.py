import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


async def test_dev_login_is_off_by_default(client, company):
    assert (await client.get("/api/v1/auth/dev-login")).json() == {"enabled": False}
    assert (await client.post("/api/v1/auth/dev-login")).status_code == 404


async def test_dev_login_signs_in_first_super_admin_when_enabled(app, client, make_user):
    admin = await make_user("root@eranova.co.ke", role="super_admin")
    local = get_settings().model_copy(update={"environment": "local", "dev_auto_login": True})
    app.dependency_overrides[get_settings] = lambda: local

    assert (await client.get("/api/v1/auth/dev-login")).json() == {"enabled": True}
    response = await client.post("/api/v1/auth/dev-login")
    assert response.status_code == 200
    assert response.json()["user"]["id"] == str(admin.id)
    assert (await client.get("/api/v1/auth/me")).status_code == 200


async def test_dev_login_creates_developer_on_empty_database(app, client, company):
    local = get_settings().model_copy(update={"environment": "local", "dev_auto_login": True})
    app.dependency_overrides[get_settings] = lambda: local
    response = await client.post("/api/v1/auth/dev-login")
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "developer@eranova.local"
    assert "role.manage" in response.json()["permissions"]


@pytest.mark.parametrize("environment", ["staging", "production", "test"])
def test_dev_login_rejected_outside_local(environment):
    with pytest.raises(ValidationError, match="DEV_AUTO_LOGIN"):
        Settings(
            database_url="postgresql://u:p@h/db",
            secret_key="x" * 40,
            environment=environment,
            session_cookie_secure=True,
            dev_auto_login=True,
            _env_file=None,
        )
