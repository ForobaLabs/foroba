"""pfh-mobile sends X-Client: native on /auth/token* and /auth/stepup/verify; the CORS
preflight must allow it, or a bundled native build (origin ionic://localhost) is blocked."""

from fastapi.testclient import TestClient

import main


def test_preflight_allows_x_client_header():
    client = TestClient(main.app)
    origin = main.ALLOWED_ORIGINS[0]
    r = client.options(
        "/auth/stepup/verify",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization,x-client",
        },
    )
    assert r.status_code == 200
    assert "x-client" in r.headers["access-control-allow-headers"].lower()
