# tests/test_unit_routes.py
import json

import app.metar_mcp_server as srv
import pytest
from starlette.requests import Request

pytestmark = pytest.mark.asyncio

def _make_request(scope_overrides=None):
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/health",
        "headers": [],
        "query_string": b"",
    }
    if scope_overrides:
        scope.update(scope_overrides)
    return Request(scope, receive=lambda: None)

async def test_health_route_direct_call():
    req = _make_request()
    resp = await srv.health_check_route(req)
    assert resp.status_code == 200
    body = json.loads(resp.body.decode())
    assert body["status"] == "healthy"
    assert body["server"] == "metar-weather-mcp"
    assert "azure_config" in body

async def test_auth_token_success(fake_httpx_client):
    # POST /auth/token
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/auth/token",
        "headers": [],
        "query_string": b"",
    }
    req = Request(scope, receive=lambda: None)
    resp = await srv.issue_token(req)
    assert resp.status_code == 200
    body = json.loads(resp.body.decode())
    assert "access_token" in body
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 3600

# tests/test_unit_routes.py (add)
import json
import types

import app.metar_mcp_server as srv
import pytest
from starlette.requests import Request


@pytest.mark.asyncio
async def test_auth_token_azure_exception(monkeypatch):
    class _BoomClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw):
            raise RuntimeError("network down")

    monkeypatch.setattr(srv.httpx, "AsyncClient", lambda timeout=None: _BoomClient())

    req = Request({"type":"http","http_version":"1.1","method":"POST","path":"/auth/token","headers":[],"query_string":b""}, receive=lambda: None)
    resp = await srv.issue_token(req)
    body = json.loads(resp.body.decode())
    assert resp.status_code == 502
    assert body["error"] == "azure_token_request_failed"

@pytest.mark.asyncio
async def test_auth_token_azure_non_200(monkeypatch):
    class _Resp:
        def __init__(self): self.status_code, self.text = 401, "AADSTS-SAMPLE"
        def json(self): return {}
    class _Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw): return _Resp()

    monkeypatch.setattr(srv.httpx, "AsyncClient", lambda timeout=None: _Client())

    req = Request({"type":"http","http_version":"1.1","method":"POST","path":"/auth/token","headers":[],"query_string":b""}, receive=lambda: None)
    resp = await srv.issue_token(req)
    body = json.loads(resp.body.decode())
    assert resp.status_code == 401
    assert body["error"] == "azure_token_error"
    assert "AADSTS" in body["azure_body"]
