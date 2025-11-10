# tests/test_unit_routes.py
import json
import pytest
from starlette.requests import Request

import app.metar_mcp_server as srv

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
