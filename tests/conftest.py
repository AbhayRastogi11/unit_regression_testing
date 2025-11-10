# tests/conftest.py
import os
import json
import types
import asyncio
import pytest
from freezegun import freeze_time

# Import your server symbols
import app.metar_mcp_server as srv

from .fake_mongo import FakeMongoClient, FakeDB

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
def set_env_vars(monkeypatch):
    # Safe defaults to avoid crashes
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
    with freeze_time("2025-11-10 10:00:00"):  # Asia/Kolkata local ~ 10:00 assumed
        yield

@pytest.fixture()
async def fake_db(monkeypatch):
    """
    Patch get_mongodb_client() to return a Fake client+db with in-memory data.
    """
    fake_client = FakeMongoClient()
    fake_db = FakeDB()

    async def _fake_get_mongodb_client():
        return fake_client, fake_db

    monkeypatch.setattr(srv, "get_mongodb_client", _fake_get_mongodb_client)
    # Ensure module-level globals align if referenced
    monkeypatch.setattr(srv, "client", fake_client, raising=False)
    monkeypatch.setattr(srv, "db", fake_db, raising=False)

    return fake_db

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

## abhay - code 

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
