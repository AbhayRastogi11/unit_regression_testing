# tests/test_unit_tools.py
import pytest
import app.metar_mcp_server as srv

pytestmark = pytest.mark.asyncio

async def test_ping_tool_returns_pong():
    assert await srv.ping() == "🏓 Pong! Authentication working correctly."

async def test_search_by_icao(fake_db, sample_docs):
    out = await srv.search_metar_data(station_icao="VOTP", limit=5)
    assert "Station: VOTP" in out
    assert "TAF" in out

async def test_search_hours_back(fake_db, sample_docs, frozen_time):
    # hours_back=2 should exclude VOBG (3h) and include VOTP (5m)
    out = await srv.search_metar_data(hours_back=2, limit=10)
    assert "Station: VOTP" in out
    assert "VOBG" not in out

async def test_search_weather_condition_exact(fake_db, sample_docs):
    # Your code does equality on weatherConditions, so TSRA should match only VOBG
    out = await srv.search_metar_data(weather_condition="TSRA", limit=10)
    assert "Station: VOBG" in out
    assert "Station: VOTP" not in out

async def test_search_no_results_message(fake_db, sample_docs):
    out = await srv.search_metar_data(station_icao="XXXX", limit=5)
    assert out.startswith("No METAR data found")
    assert "ICAO: XXXX" in out

async def test_list_available_stations(fake_db, sample_docs):
    out = await srv.list_available_stations()
    assert "ICAO Codes" in out
    assert "VOTP" in out and "VOBG" in out and "VIDP" in out
    assert "IATA Codes" in out
    assert "TIR" in out and "BLR" in out and "DEL" in out

async def test_get_metar_statistics(fake_db, sample_docs):
    out = await srv.get_metar_statistics()
    assert "METAR Database Statistics" in out
    assert "Unique ICAO Codes" in out
    assert "Reports with METAR" in out

async def test_raw_mongodb_query_parsing(fake_db, sample_docs):
    query = '{"stationICAO": "VOTP"}'
    out = await srv.raw_mongodb_query(query_json=query, limit=5)
    assert "Query: {\"stationICAO\": \"VOTP\"}" in out
    assert "Station: VOTP" in out

async def test_raw_mongodb_query_invalid_json(fake_db):
    out = await srv.raw_mongodb_query(query_json="{bad json")
    assert out.startswith("Invalid JSON query")

