# === Add this block at the VERY TOP of tests/conftest.py ===
import os
import sys
import types

# Stub "fastmcp" with minimal API used by your server
fastmcp_mod = types.ModuleType("fastmcp")

class _FastMCPStub:
    def __init__(self, name, auth=None):
        self.name = name
        self.auth = auth
        self.app = None  # optional; used only if you do ASGI tests

    def tool(self, *args, **kwargs):
        def _decorator(fn):
            return fn
        return _decorator

    def resource(self, *args, **kwargs):
        def _decorator(fn):
            return fn
        return _decorator

    def custom_route(self, *args, **kwargs):
        def _decorator(fn):
            return fn
        return _decorator

    def run(self, *args, **kwargs):
        # no-op in tests
        pass

fastmcp_mod.FastMCP = _FastMCPStub
sys.modules["fastmcp"] = fastmcp_mod

# Stub "fastmcp.server.auth.providers.jwt.JWTVerifier"
server_mod = types.ModuleType("fastmcp.server")
auth_mod = types.ModuleType("fastmcp.server.auth")
providers_mod = types.ModuleType("fastmcp.server.auth.providers")
jwt_mod = types.ModuleType("fastmcp.server.auth.providers.jwt")

class _JWTVerifierStub:
    def __init__(self, jwks_uri=None, issuer=None, audience=None):
        self.jwks_uri = jwks_uri
        self.issuer = issuer
        self.audience = audience

jwt_mod.JWTVerifier = _JWTVerifierStub

sys.modules["fastmcp.server"] = server_mod
sys.modules["fastmcp.server.auth"] = auth_mod
sys.modules["fastmcp.server.auth.providers"] = providers_mod
sys.modules["fastmcp.server.auth.providers.jwt"] = jwt_mod
# === end stub block ===

# 🔧 Set required env vars BEFORE importing your server (module reads them on import)
os.environ.setdefault("PORT", "8001")
os.environ.setdefault("TENANT_ID", "test-tenant")
os.environ.setdefault("APP_ID", "00000000-0000-0000-0000-000000000000")
os.environ.setdefault("CLIENT_SECRET", "fake-secret")
os.environ.setdefault("MONGODB_URL", "mongodb://localhost:27017")
os.environ.setdefault("DATABASE_NAME", "metar_data")
os.environ.setdefault("COLLECTION_METAR", "metar_data")

# Now it's safe to import your server and other deps
import json

import app.metar_mcp_server as srv
import pytest
from freezegun import freeze_time

from .fake_mongo import FakeDB, FakeMongoClient


@pytest.fixture(autouse=True)
def set_env_vars(monkeypatch):
    # Keep things consistent during tests too
    monkeypatch.setenv("PORT", "8001")
    monkeypatch.setenv("TENANT_ID", "test-tenant")
    monkeypatch.setenv("APP_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("CLIENT_SECRET", "fake-secret")
    monkeypatch.setenv("MONGODB_URL", "mongodb://localhost:27017")
    monkeypatch.setenv("DATABASE_NAME", "metar_data")
    monkeypatch.setenv("COLLECTION_METAR", "metar_data")


@pytest.fixture()
def frozen_time():
    # Keep tests deterministic
    with freeze_time("2025-11-10 10:00:00"):
        yield


# ✅ SYNC fixture (not async) — earlier async fixture caused "never awaited" issues
@pytest.fixture()
def fake_db(monkeypatch):
    """
    Patch get_mongodb_client() to return a Fake client+db with in-memory data.
    """
    fake_client = FakeMongoClient()
    _fake_db = FakeDB()

    async def _fake_get_mongodb_client():
        return fake_client, _fake_db

    monkeypatch.setattr(srv, "get_mongodb_client", _fake_get_mongodb_client)
    # Ensure module-level globals align if referenced
    monkeypatch.setattr(srv, "client", fake_client, raising=False)
    monkeypatch.setattr(srv, "db", _fake_db, raising=False)

    return _fake_db


@pytest.fixture()
def sample_docs(fake_db):
    """
    Load sample METAR/TAF docs into fake DB.
    """
    from .fixtures_sample_data import SAMPLE_DOCS
    fake_db.collections["metar_data"].extend(SAMPLE_DOCS)
    return SAMPLE_DOCS


@pytest.fixture()
def fake_httpx_client(monkeypatch):
    """
    Monkeypatch httpx.AsyncClient within /auth/token to return predictable results.
    """

    class _Resp:
        def __init__(self, status_code, json_body=None, text=""):
            self.status_code = status_code
            self._json = json_body or {}
            self.text = text

        def json(self):
            return self._json

    class _FakeAsyncClient:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, data=None):
            if "oauth2/v2.0/token" in url:
                # success
                return _Resp(
                    200,
                    {
                        "access_token": "fake_access_token",
                        "expires_in": 3600,
                        "token_type": "Bearer",
                    }
                )
            return _Resp(404, text="Not found")

    monkeypatch.setattr(srv.httpx, "AsyncClient", _FakeAsyncClient)
    return True
