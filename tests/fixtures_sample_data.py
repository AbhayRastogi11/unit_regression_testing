# tests/fixtures_sample_data.py
from datetime import datetime, timedelta

NOW = datetime(2025, 11, 10, 10, 0, 0)  # aligned with freeze_time in tests

SAMPLE_DOCS = [
    {
        "_id": "1",
        "stationICAO": "VOTP",
        "stationIATA": "TIR",
        "hasMetarData": True,
        "hasTaforData": True,
        "processed_timestamp": NOW - timedelta(minutes=5),
        "timestamp": NOW - timedelta(minutes=5),
        "metar": {
            "updatedTime": NOW - timedelta(minutes=5),
            "firRegion": "Chennai",
            "rawData": "VOTP 101000Z 09008KT 6000 FEW020 30/22 Q1008 NOSIG",
            "decodedData": {
                "observation": {
                    "observationTimeUTC": NOW - timedelta(minutes=5),
                    "observationTimeIST": NOW - timedelta(minutes=5),
                    "windSpeed": "8",
                    "windDirection": "090",
                    "horizontalVisibility": "6000",
                    "weatherConditions": None,
                    "cloudLayers": ["FEW020"],
                    "airTemperature": "30",
                    "dewpointTemperature": "22",
                    "observedQNH": "1008",
                    "runwayVisualRange": None,
                    "windShear": None,
                    "runwayConditions": None,
                }
            }
        },
        "tafor": {"rawData": "TAF VOTP 101000Z ...", "updatedTime": None, "timestamp": NOW},
    },
    {
        "_id": "2",
        "stationICAO": "VOBG",
        "stationIATA": "BLR",
        "hasMetarData": True,
        "hasTaforData": False,
        "timestamp": NOW - timedelta(hours=3),
        "metar": {
            "updatedTime": NOW - timedelta(hours=3),
            "firRegion": "Mumbai",
            "rawData": "VOBG 100700Z 27015KT 3000 TSRA SCT030 26/23 Q1004",
            "decodedData": {
                "observation": {
                    "observationTimeUTC": NOW - timedelta(hours=3),
                    "observationTimeIST": NOW - timedelta(hours=3),
                    "windSpeed": "15",
                    "windDirection": "270",
                    "horizontalVisibility": "3000",
                    "weatherConditions": "TSRA",
                    "cloudLayers": ["SCT030"],
                    "airTemperature": "26",
                    "dewpointTemperature": "23",
                    "observedQNH": "1004",
                }
            }
        },
        "tafor": {"rawData": "", "updatedTime": None, "timestamp": NOW - timedelta(hours=3)},
    },
    {
        "_id": "3",
        "stationICAO": "VIDP",
        "stationIATA": "DEL",
        "hasMetarData": False,
        "hasTaforData": False,
        "timestamp": NOW - timedelta(days=1),
        "metar": {
            "updatedTime": NOW - timedelta(days=1),
            "firRegion": "Delhi",
            "rawData": "VIDP 091000Z CAVOK 28/12 Q1012",
            "decodedData": {"observation": {}}
        },
        "tafor": {"rawData": "", "updatedTime": None, "timestamp": NOW - timedelta(days=1)},
    },
]
