# tests/test_unit_tools.py
import app.metar_mcp_server as srv
import pytest

pytestmark = pytest.mark.asyncio


# ✅ Temperature-only range should include both VOTP (30C) and VOBG (26C)
async def test_search_temp_range_only(fake_db, sample_docs):
    out = await srv.search_metar_data(temperature_min=25, temperature_max=30, limit=10)
    assert "VOTP" in out and "VOBG" in out

# ✅ Cloud-only regex FEW should include VOTP
async def test_search_cloud_regex_only_few(fake_db, sample_docs):
    out = await srv.search_metar_data(cloud_type="FEW", limit=10)
    assert "VOTP" in out
    assert "VOBG" not in out  # VOBG has SCT030 not FEW

# ✅ Cloud-only regex SCT should include VOBG
async def test_search_cloud_regex_only_sct(fake_db, sample_docs):
    out = await srv.search_metar_data(cloud_type="SCT", limit=10)
    assert "VOBG" in out
    assert "VOTP" not in out  # VOTP has FEW020 not SCT


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

async def test_formatting_missing_fields(fake_db):
    doc = {
        "_id":"x",
        "stationICAO":"TEST",
        "stationIATA":None,
        "hasMetarData":True,
        "hasTaforData":False,
        "metar":{
            "updatedTime": None,
            "firRegion":"Nowhere",
            "rawData":"TEST 101000Z //// ///// ///// //// Q////",
            "decodedData":{
                "observation":{
                    # omit airTemperature, dewpointTemperature, cloudLayers (None), weatherConditions (None)
                    "windSpeed": None,
                    "windDirection": None,
                    "horizontalVisibility": None,
                    "observedQNH": None,
                    "cloudLayers": None,
                    "weatherConditions": None,
                }
            }
        },
        "timestamp": None,
    }
    fake_db.collections["metar_data"].append(doc)
    out = await srv.search_metar_data(station_icao="TEST", limit=1)
    # Should not crash, should print N/A lines
    assert "Temperature: N/A" in out
    assert "Clouds:" not in out  # cloudLayers is None so no Clouds line

async def test_statistics_empty_db(fake_db):
    # clear all docs
    fake_db.collections["metar_data"].clear()
    out = await srv.get_metar_statistics()
    # should show zeros and not crash on earliest/latest
    assert "METAR Reports: 0" in out
    assert "Earliest:" not in out and "Latest:" not in out

async def test_raw_query_no_results(fake_db, sample_docs):
    out = await srv.raw_mongodb_query('{"stationICAO":"XXXX"}', limit=5)
    assert "No documents found matching query" in out

# FEW + temp range => VOTP milna chahiye

async def test_statistics_empty_db(fake_db):
    # clear all docs
    fake_db.collections["metar_data"].clear()
    out = await srv.get_metar_statistics()
    # should show zeros and not crash on earliest/latest
    assert "METAR Reports: 0" in out
    assert "Earliest:" not in out and "Latest:" not in out
