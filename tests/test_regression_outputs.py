# tests/test_regression_outputs.py
import pytest
import app.metar_mcp_server as srv

pytestmark = pytest.mark.asyncio

async def test_search_output_snapshot(fake_db, sample_docs, frozen_time, snapshot):
    out = await srv.search_metar_data(station_icao="VOTP", limit=2)
    assert out == snapshot

async def test_list_stations_snapshot(fake_db, sample_docs, snapshot):
    out = await srv.list_available_stations()
    assert out == snapshot

async def test_statistics_snapshot(fake_db, sample_docs, snapshot):
    out = await srv.get_metar_statistics()
    assert out == snapshot

async def test_raw_query_snapshot(fake_db, sample_docs, snapshot):
    out = await srv.raw_mongodb_query(query_json='{"stationICAO": "VOBG"}', limit=5)
    assert out == snapshot
