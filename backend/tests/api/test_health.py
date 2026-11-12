async def test_health_is_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_ready_checks_database(client, engine):
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok"}


async def test_responses_carry_correlation_id_and_security_headers(client):
    response = await client.get("/health", headers={"X-Correlation-ID": "abc12345-test"})
    assert response.headers["X-Correlation-ID"] == "abc12345-test"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


async def test_invalid_correlation_id_is_replaced(client):
    response = await client.get("/health", headers={"X-Correlation-ID": "bad id<script>"})
    assert response.headers["X-Correlation-ID"] != "bad id<script>"


async def test_unknown_route_uses_error_envelope(client):
    response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["correlation_id"]


async def test_disallowed_origin_rejected_for_unsafe_methods(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "a@b.co", "password": "x"},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_not_allowed"


async def test_cors_allows_configured_origin_with_credentials(client):
    response = await client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-csrf-token",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"
