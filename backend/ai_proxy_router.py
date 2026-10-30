"""AI settings proxy (Plan AV T7): the web/mobile clients talk to Foroba only; every call is
forwarded 1:1 to the ai-gateway with the caller's session JWT. Request bodies are never logged
(PUT /byok carries an API key)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Cookie, Depends, Header, Request
from fastapi.responses import JSONResponse, Response

from ai_gateway_client import GatewayRejected, GatewayUnavailable, get_client
from auth.dependencies import _token_from_header, get_current_user, require_admin

router = APIRouter(prefix="/ai", tags=["ai"])


def _jwt(authorization: str | None, suite_session: str | None) -> str:
    return _token_from_header(authorization) or suite_session or ""


async def _json_body(request: Request) -> Any:
    try:
        return await request.json()
    except ValueError:
        return None


async def _forward(
    method: str,
    request: Request,
    path: str,
    authorization,
    suite_session,
    *,
    body: bool = False,
    params: bool = False,
):
    client = get_client()
    jwt = _jwt(authorization, suite_session)
    try:
        out = await client.request(
            method,
            jwt,
            path,
            await _json_body(request) if body else None,
            dict(request.query_params) if params else None,
        )
    except GatewayRejected as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status)
    except GatewayUnavailable:
        return JSONResponse({"detail": {"code": "ai_gateway_unavailable"}}, status_code=503)
    if out is None:
        return Response(status_code=204)
    return JSONResponse(out)


_Auth = Header(default=None)
_Cookie = Cookie(default=None)


@router.get("/prefs")
async def get_prefs(
    request: Request,
    _u: dict = Depends(get_current_user),
    authorization: str | None = _Auth,
    suite_session: str | None = _Cookie,
):
    return await _forward("GET", request, "/v1/prefs", authorization, suite_session)


@router.put("/prefs")
async def put_prefs(
    request: Request,
    _u: dict = Depends(get_current_user),
    authorization: str | None = _Auth,
    suite_session: str | None = _Cookie,
):
    return await _forward("PUT", request, "/v1/prefs", authorization, suite_session, body=True)


@router.get("/consents")
async def get_consents(
    request: Request,
    _u: dict = Depends(get_current_user),
    authorization: str | None = _Auth,
    suite_session: str | None = _Cookie,
):
    return await _forward("GET", request, "/v1/consents", authorization, suite_session)


@router.post("/consents")
async def post_consent(
    request: Request,
    _u: dict = Depends(get_current_user),
    authorization: str | None = _Auth,
    suite_session: str | None = _Cookie,
):
    return await _forward("POST", request, "/v1/consents", authorization, suite_session, body=True)


@router.delete("/consents/{provider:path}")
async def delete_consent(
    provider: str,
    request: Request,
    _u: dict = Depends(get_current_user),
    authorization: str | None = _Auth,
    suite_session: str | None = _Cookie,
):
    return await _forward(
        "DELETE", request, f"/v1/consents/{provider}", authorization, suite_session
    )


@router.get("/byok")
async def get_byok(
    request: Request,
    _u: dict = Depends(get_current_user),
    authorization: str | None = _Auth,
    suite_session: str | None = _Cookie,
):
    return await _forward("GET", request, "/v1/byok", authorization, suite_session)


@router.put("/byok")
async def put_byok(
    request: Request,
    _u: dict = Depends(get_current_user),
    authorization: str | None = _Auth,
    suite_session: str | None = _Cookie,
):
    return await _forward("PUT", request, "/v1/byok", authorization, suite_session, body=True)


@router.delete("/byok/{provider}")
async def delete_byok(
    provider: str,
    request: Request,
    _u: dict = Depends(get_current_user),
    authorization: str | None = _Auth,
    suite_session: str | None = _Cookie,
):
    return await _forward("DELETE", request, f"/v1/byok/{provider}", authorization, suite_session)


@router.post("/byok/{provider}/test")
async def test_byok(
    provider: str,
    request: Request,
    _u: dict = Depends(get_current_user),
    authorization: str | None = _Auth,
    suite_session: str | None = _Cookie,
):
    return await _forward(
        "POST", request, f"/v1/byok/{provider}/test", authorization, suite_session
    )


@router.get("/usage")
async def get_usage(
    request: Request,
    _u: dict = Depends(get_current_user),
    authorization: str | None = _Auth,
    suite_session: str | None = _Cookie,
):
    return await _forward("GET", request, "/v1/usage", authorization, suite_session, params=True)


@router.get("/admin/usage")
async def get_admin_usage(
    request: Request,
    _a: dict = Depends(require_admin),
    authorization: str | None = _Auth,
    suite_session: str | None = _Cookie,
):
    return await _forward(
        "GET", request, "/v1/admin/usage", authorization, suite_session, params=True
    )
