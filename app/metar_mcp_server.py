import json
import os
import time
from datetime import datetime, timedelta
from typing import Any

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier  # type: ignore[import-not-found]
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.requests import Request
from starlette.responses import JSONResponse

# Load environment variables from .env file
load_dotenv()

# MongoDB configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "metar_data")
COLLECTION_METAR = os.getenv("COLLECTION_METAR", "metar_data")

# ------------------- Config (server-only secrets) -------------------
TENANT_ID = os.getenv("TENANT_ID")
APP_ID = os.getenv("APP_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
PORT = 8000

# OpenID metadata
JWKS_URI = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
AUDIENCE = APP_ID

# ------------------- MCP with JWT verification ----------------------
auth = JWTVerifier(
    jwks_uri=JWKS_URI,
    issuer=ISSUER,
    audience=AUDIENCE,
)

mcp = FastMCP(name="metar-weather", auth=auth)

# Global MongoDB client
client: AsyncIOMotorClient | None = None
db: Any | None = None


async def get_mongodb_client() -> tuple[Any, Any]:
    """Get MongoDB client connection."""
    global client, db
    if client is None:
        client = AsyncIOMotorClient(MONGODB_URL)
        db = client[DATABASE_NAME]
    # mypy: db is set together with client above
    return client, db  # type: ignore[return-value]


def format_metar_data(metar_doc: dict[str, Any]) -> str:
    """Format METAR data into a readable string."""
    station = metar_doc.get('stationICAO', 'Unknown')
    iata = metar_doc.get('stationIATA', 'N/A')
    processed_timestamp = metar_doc.get('processed_timestamp', 'Unknown')

    result = f"🛩️ Station: {station}"
    if iata:
        result += f" ({iata})"
    result += f"\n Last Updated: {processed_timestamp}\n"

    if metar_doc.get('hasMetarData') and 'metar' in metar_doc:
        metar = metar_doc['metar']
        raw_data = metar.get('rawData', 'N/A')
        result += f" Raw METAR: {raw_data}\n"

        if 'decodedData' in metar and 'observation' in metar['decodedData']:
            obs = metar['decodedData']['observation']
            result += "\n Weather Conditions:\n"
            result += f" Temperature: {obs.get('airTemperature', 'N/A')}\n"
            result += f" Dewpoint: {obs.get('dewpointTemperature', 'N/A')}\n"
            wind_speed = obs.get('windSpeed', 'N/A')
            wind_dir = obs.get('windDirection', 'N/A')
            result += f" Wind: {wind_speed} from {wind_dir}\n"
            result += f" Visibility: {obs.get('horizontalVisibility', 'N/A')}\n"
            result += f" Pressure: {obs.get('observedQNH', 'N/A')}\n"

            if obs.get('cloudLayers'):
                result += f" Clouds: {', '.join(obs['cloudLayers'])}\n"

            if obs.get('weatherConditions'):
                result += f" Weather: {obs['weatherConditions']}\n"

    if metar_doc.get('hasTaforData') and 'tafor' in metar_doc:
        tafor = metar_doc['tafor']
        raw_taf = tafor.get('rawData', 'N/A')
        result += f"\n📊 TAF: {raw_taf}\n"

    return result


@mcp.resource("resource://metar_json_schema")
async def metar_format():
    """Get the JSON schema for METAR data documents."""
    schema = {
        "_id": "ObjectId",
        "stationICAO": "String",
        "stationIATA": "String",
        "hasMetarData": "Boolean",
        "hasTaforData": "Boolean",
        "metar": {
            "updatedTime": "DateTime (ISO 8601)",
            "firRegion": "String",
            "rawData": "String",
            "decodedData": {
                "observation": {
                    "observationTimeUTC": "DateTime (ISO 8601)",
                    "observationTimeIST": "DateTime (ISO 8601)",
                    "windSpeed": "String",
                    "windDirection": "String",
                    "horizontalVisibility": "String",
                    "weatherConditions": "Null",
                    "cloudLayers": ["String"],
                    "airTemperature": "String",
                    "dewpointTemperature": "String",
                    "observedQNH": "String",
                    "runwayVisualRange": "Null",
                    "windShear": "Null",
                    "runwayConditions": "Null"
                },
                "additionalInformation": {
                    "weatherTrend": "Null",
                    "forecastWeather": "Null"
                },
                "tempoSection": {
                    "type": "Null",
                    "timePeriod": "Null",
                    "windSpeed": "Null",
                    "windDirection": "Null",
                    "visibility": "Null",
                    "weatherConditions": "Null"
                }
            }
        },
        "tafor": {
            "rawData": "String",
            "updatedTime": "Null",
            "timestamp": "DateTime (ISO 8601)"
        }
    }
    return schema


@mcp.tool()
async def search_metar_data(
    station_icao: str | None = None,
    station_iata: str | None = None,
    weather_condition: str | None = None,
    temperature_min: float | None = None,
    temperature_max: float | None = None,
    visibility_min: int | None = None,
    visibility_max: int | None = None,
    wind_speed_min: float | None = None,
    wind_speed_max: float | None = None,
    pressure_min: float | None = None,
    pressure_max: float | None = None,
    cloud_type: str | None = None,
    fir_region: str | None = None,
    hours_back: int | None = None,
    limit: int = 10
) -> str:
    """Generic search for METAR data with multiple optional filters.

    Args:
    station_icao: Filter by ICAO code (e.g., 'VOTP', 'VIDP', 'VOBG')
    station_iata: Filter by IATA code (e.g., 'TIR', 'BOM', 'DEL')
    weather_condition: Search in raw METAR data (e.g., 'Rain', 'fog', 'CB')
    temperature_min: Minimum temperature in Celsius
    temperature_max: Maximum temperature in Celsius
    visibility_min: Minimum visibility in meters
    visibility_max: Maximum visibility in meters
    wind_speed_min: Minimum wind speed in m/s
    wind_speed_max: Maximum wind speed in m/s
    pressure_min: Minimum pressure in hPa
    pressure_max: Maximum pressure in hPa
    cloud_type: Search for cloud types in raw data (e.g., 'CB', 'SCT', 'OVC')
    fir_region: Filter by FIR region (e.g., 'Chennai', 'Mumbai')
    hours_back: Look back N hours from now
    limit: Maximum results to return (set default as: 10, max: 50)
    """
    try:
        _, db = await get_mongodb_client()

        # Build the query
        query: dict[str, Any] = {}

        # Station filters
        if station_icao:
            query["stationICAO"] = station_icao.upper()
        if station_iata:
            query["stationIATA"] = station_iata.upper()

        # FIR region filter
        if fir_region:
            query["metar.firRegion"] = {"$regex": fir_region, "$options": "i"}

        # Time filter
        if hours_back:
            time_threshold = datetime.now() - timedelta(hours=hours_back)
            query["timestamp"] = {"$gte": time_threshold}

        # Weather condition filter (search in raw METAR data)
        if weather_condition:
            query["metar.decodedData.observation.weatherConditions"] = weather_condition

        # Cloud type filter (search in raw METAR data)
        if cloud_type:
            query["metar.rawData"] = {"$regex": cloud_type, "$options": "i"}

        # Temperature filters
        if (temperature_min is not None) or (temperature_max is not None):
            temp_query: dict[str, Any] = {}
            if temperature_min is not None:
                temp_query["$gte"] = str(temperature_min)
            if temperature_max is not None:
                temp_query["$lte"] = str(temperature_max)
            query["metar.decodedData.observation.airTemperature"] = temp_query

        # Visibility filters
        if (visibility_min is not None) or (visibility_max is not None):
            vis_query: dict[str, Any] = {}
            if visibility_min is not None:
                vis_query["$gte"] = str(visibility_min)
            if visibility_max is not None:
                vis_query["$lte"] = str(visibility_max)
            query["metar.decodedData.observation.horizontalVisibility"] = vis_query

        # Wind speed filters
        if (wind_speed_min is not None) or (wind_speed_max is not None):
            wind_query: dict[str, Any] = {}
            if wind_speed_min is not None:
                wind_query["$gte"] = str(wind_speed_min)
            if wind_speed_max is not None:
                wind_query["$lte"] = str(wind_speed_max)
            query["metar.decodedData.observation.windSpeed"] = wind_query

        # Pressure filters
        if (pressure_min is not None) or (pressure_max is not None):
            pressure_query: dict[str, Any] = {}
            if pressure_min is not None:
                pressure_query["$gte"] = str(pressure_min)
            if pressure_max is not None:
                pressure_query["$lte"] = str(pressure_max)
            query["metar.decodedData.observation.observedQNH"] = pressure_query

        # Limit results
        limit = min(limit, 50)

        # Execute the query
        print(f"🔍 Executing MongoDB query: {query}")
        cursor = db[COLLECTION_METAR].find(query).sort("timestamp", -1).limit(limit)
        results = await cursor.to_list(length=limit)

        if not results:
            filters = []
            if station_icao:
                filters.append(f"ICAO: {station_icao}")
            if station_iata:
                filters.append(f"IATA: {station_iata}")
            if weather_condition:
                filters.append(f"Weather: {weather_condition}")
            if temperature_min is not None:
                filters.append(f"Temp ≥ {temperature_min}°C")
            if temperature_max is not None:
                filters.append(f"Temp ≤ {temperature_max}°C")
            if visibility_min is not None:
                filters.append(f"Visibility ≥ {visibility_min}m")
            if visibility_max is not None:
                filters.append(f"Visibility ≤ {visibility_max}m")
            if wind_speed_min is not None:
                filters.append(f"Wind ≥ {wind_speed_min} m/s")
            if wind_speed_max is not None:
                filters.append(f"Wind ≤ {wind_speed_max} m/s")
            if pressure_min is not None:
                filters.append(f"Pressure ≥ {pressure_min} hPa")
            if pressure_max is not None:
                filters.append(f"Pressure ≤ {pressure_max} hPa")
            if cloud_type:
                filters.append(f"Cloud: {cloud_type}")
            if fir_region:
                filters.append(f"FIR: {fir_region}")
            if hours_back:
                filters.append(f"Last {hours_back}h")

            return f"No METAR data found with filters: {', '.join(filters)}"

        # Format results
        result = f"🔍 METAR Search Results ({len(results)} documents found):\n"
        applied_filters = [
            f"{k}: {v}"
            for k, v in locals().items()
            if (v is not None) and (k not in ['db', 'cursor', 'results', 'limit', 'hours_back', 'query'])
        ]


        if applied_filters:
            result += f"Filters: {', '.join(applied_filters)}\n"
        result += "=" * 80 + "\n\n"

        for i, doc in enumerate(results, 1):
            result += f"--- Result {i} ---\n"
            result += format_metar_data(doc)
            result += "\n"

        return result

    except Exception as e:
        print(f"❌ Error in search_metar_data: {e}")
        return f"Error executing search: {str(e)}"


@mcp.tool()
async def list_available_stations() -> str:
    """List all available weather stations with their codes."""
    try:
        _, db = await get_mongodb_client()

        # Get unique ICAO codes
        icao_codes = await db[COLLECTION_METAR].distinct("stationICAO")
        icao_codes.sort()

        # Get unique IATA codes (non-null)
        iata_codes = await db[COLLECTION_METAR].distinct("stationIATA")
        iata_codes = [code for code in iata_codes if code is not None]
        iata_codes.sort()

        # Get station count
        total_stations = await db[COLLECTION_METAR].count_documents({})

        result = f"📡 Available Weather Stations ({total_stations} total reports)\n"
        result += "=" * 50 + "\n\n"

        result += f"🛩️ ICAO Codes ({len(icao_codes)} stations):\n"
        for i, code in enumerate(icao_codes, 1):
            result += f" {i:3d}. {code}"
            if i % 10 == 0:
                result += "\n"
            else:
                result += " "
        if len(icao_codes) % 10 != 0:
            result += "\n"

        result += f"\n🏢 IATA Codes ({len(iata_codes)} stations):\n"
        for i, code in enumerate(iata_codes, 1):
            result += f" {i:3d}. {code}"
            if i % 10 == 0:
                result += "\n"
            else:
                result += " "
        if len(iata_codes) % 10 != 0:
            result += "\n"

        return result

    except Exception as e:
        print(f"❌ Error in list_available_stations: {e}")
        return f"Error retrieving station list: {str(e)}"


@mcp.tool()
async def get_metar_statistics() -> str:
    """Get statistics about the METAR database."""
    try:
        _, db = await get_mongodb_client()

        # Get basic counts
        total_metar = await db[COLLECTION_METAR].count_documents({})

        # Get unique station counts
        unique_icao = len(await db[COLLECTION_METAR].distinct("stationICAO"))
        iata_list = await db[COLLECTION_METAR].distinct("stationIATA")
        unique_iata = len([code for code in iata_list if code is not None])

        # Get date range
        earliest = (
            await db[COLLECTION_METAR]
            .find({}, {"metar.updatedTime": 1})
            .sort("metar.updatedTime", 1)
            .limit(1)
            .to_list(1)
        )
        latest = (
            await db[COLLECTION_METAR]
            .find({}, {"metar.updatedTime": 1})
            .sort("metar.updatedTime", -1)
            .limit(1)
            .to_list(1)
        )

        # Get data availability
        with_metar = await db[COLLECTION_METAR].count_documents({"hasMetarData": True})
        with_taf = await db[COLLECTION_METAR].count_documents({"hasTaforData": True})

        # ✅ Guard: avoid ZeroDivisionError
        def pct(n: int) -> float:
            return (n / total_metar * 100) if total_metar else 0.0

        result = "📊 METAR Database Statistics\n"
        result += "=" * 40 + "\n\n"

        result += "📈 Document Counts:\n"
        result += f" METAR Reports: {total_metar:,}\n\n"

        result += "🛩️ Station Information:\n"
        result += f" Unique ICAO Codes: {unique_icao}\n"
        result += f" Unique IATA Codes: {unique_iata}\n\n"

        result += "📅 Data Range:\n"
        if earliest:
            result += f" Earliest: {earliest[0]['metar']['updatedTime']}\n"
        if latest:
            result += f" Latest: {latest[0]['metar']['updatedTime']}\n\n"

        result += "✅ Availability:\n"
        result += f" Reports with METAR: {with_metar:,} ({pct(with_metar):.1f}%)\n"
        result += f" Reports with TAF: {with_taf:,} ({pct(with_taf):.1f}%)\n"

        return result

    except Exception as e:
        print(f"❌ Error in get_metar_statistics: {e}")
        return f"Error retrieving statistics: {str(e)}"


@mcp.tool()
async def raw_mongodb_query(query_json: str, limit: int = 10) -> str:
    """Execute a raw MongoDB query against the METAR database."""
    try:
        _, db = await get_mongodb_client()

        # Parse the query JSON
        try:
            query = json.loads(query_json)
        except json.JSONDecodeError as e:
            return f"Invalid JSON query: {str(e)}\n\nExample: '{{\"stationICAO\": \"VOTP\"}}'"

        # Limit the number of results
        limit = min(limit, 50)

        print(f"🔍 Executing raw MongoDB query: {query}")
        cursor = db[COLLECTION_METAR].find(query).sort("metar.updatedTime", -1).limit(limit)
        results = await cursor.to_list(length=limit)

        if not results:
            return f"No documents found matching query: {query_json}"

        # Format results
        result = f"🔍 Raw MongoDB Query Results ({len(results)} documents found):\n"
        result += f"Query: {query_json}\n"
        result += "=" * 60 + "\n\n"

        for i, doc in enumerate(results, 1):
            result += f"--- Result {i} ---\n"
            result += format_metar_data(doc)
            result += "\n"

        return result

    except Exception as e:
        print(f"❌ Error in raw_mongodb_query: {e}")
        return f"Error executing query: {str(e)}"


@mcp.tool()
async def ping() -> str:
    """Simple ping tool for testing authentication."""
    return "🏓 Pong! Authentication working correctly."


# ------------------- Custom routes (public) -------------------------
@mcp.custom_route("/health", methods=["GET"])  # type: ignore[attr-defined]
async def health_check_route(request: Request):
    """Health check endpoint - no authentication required."""
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "server": "metar-weather-mcp",
        "azure_config": {
            "tenant_id": TENANT_ID,
            "app_id": APP_ID,
            "auth_enabled": True
        }
    })


@mcp.custom_route("/auth/token", methods=["POST"])  # type: ignore[attr-defined]
async def issue_token(request: Request):
    """
    Client yahan POST karega (no body needed).
    Server Azure se app-only token nikaal ke return karega.
    """
    print("🔐 Token request received from client")

    token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    form = {
        "client_id": APP_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials",
        "scope": f"api://{APP_ID}/.default",
    }

    print(f"🔄 Requesting token from Azure AD: {token_url}")
    print(f"📋 Form data: client_id={APP_ID}, scope=api://{APP_ID}/.default")

    try:
        async with httpx.AsyncClient(timeout=20.0) as http:
            resp = await http.post(token_url, data=form)
            print(f"🌐 Azure AD response status: {resp.status_code}")

    except Exception as e:
        print(f"❌ Azure token request failed: {e}")
        return JSONResponse(
            {"error": "azure_token_request_failed", "detail": str(e)},
            status_code=502
        )

    if resp.status_code != 200:
        print(f"❌ Azure AD error: {resp.text}")
        # Azure ka raw error dikha do (AADSTS codes) for debugging
        return JSONResponse(
            {"error": "azure_token_error", "azure_body": resp.text},
            status_code=resp.status_code
        )

    body = resp.json()
    print("✅ Successfully obtained token from Azure AD")
    print(f"📊 Token expires in: {body.get('expires_in')} seconds")

    return JSONResponse({
        "access_token": body.get("access_token"),
        "expires_in": body.get("expires_in"),
        "token_type": body.get("token_type", "Bearer"),
        "issued_at": int(time.time()),
    })


if __name__ == "__main__":
    # Initialize and run the server
    print("🚀 METAR MCP Server with Azure Authentication starting...")
    print(f"🗄️ MongoDB URL: {MONGODB_URL}")
    print(f"📊 Database: {DATABASE_NAME}")
    print(f"🏷️ Collection: {COLLECTION_METAR}")
    print(f"🔐 Azure Tenant ID: {TENANT_ID}")
    print(f"🏢 Azure App ID: {APP_ID}")
    print(f"🌐 Port: {PORT}")
    print("✅ Server ready! Waiting for HTTP requests...")

    # same port par custom routes + MCP endpoint serve honge
    mcp.run(transport="streamable-http", host="127.0.0.1", port=PORT)  # type: ignore[call-arg,arg-type]
