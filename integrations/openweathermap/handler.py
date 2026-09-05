"""
OpenWeatherMap integration.

Auth: api_key passed as `appid` query parameter.

Credential fields:
  - api_key (str) : OpenWeatherMap API key.

Nodes:
  - openweathermap.get_current_weather : Current weather for a city / coords.
  - openweathermap.get_forecast        : 5-day / 3-hour forecast.
  - openweathermap.get_air_quality     : Air pollution / quality index.

Base URL: https://api.openweathermap.org/data/2.5/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.openweathermap.org/data/2.5/"


async def _get_api_key(credential_id: str, db) -> str:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("OpenWeatherMap credential missing 'api_key'")
    return api_key


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"OpenWeatherMap API error {r.status_code}: {detail}")


def _location_params(config: dict, input_data: dict) -> dict:
    """Build location query params from config/input.

    Accepts:
      - city (str)         — city name, e.g. "Berlin" or "Berlin,DE"
      - lat + lon (float)  — explicit coordinates
      - zip (str)          — zip code, e.g. "10115,DE"
    """
    city = config.get("city") or input_data.get("city")
    lat = config.get("lat") or input_data.get("lat")
    lon = config.get("lon") or input_data.get("lon")
    zip_code = config.get("zip") or input_data.get("zip")

    if lat is not None and lon is not None:
        return {"lat": lat, "lon": lon}
    if zip_code:
        return {"zip": zip_code}
    if city:
        return {"q": city}
    raise ValueError("Provide one of: 'city', 'lat'+'lon', or 'zip'")


@register_node("openweathermap.get_current_weather")
async def get_current_weather(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Fetch current weather conditions.

    Config / input keys:
      - city / lat+lon / zip (required) : Location selector.
      - units (str)                     : metric | imperial | standard. Default metric.
      - lang (str)                      : Language code. Default en.
    """
    api_key = await _get_api_key(credential_id, db)
    units = config.get("units") or input_data.get("units", "metric")
    lang = config.get("lang") or input_data.get("lang", "en")

    params = _location_params(config, input_data)
    params.update({"appid": api_key, "units": units, "lang": lang})

    log.info("openweathermap.get_current_weather", params={k: v for k, v in params.items() if k != "appid"})
    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=20.0) as client:
        r = await client.get("weather", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "city": data.get("name"),
        "country": data.get("sys", {}).get("country"),
        "temperature": data.get("main", {}).get("temp"),
        "feels_like": data.get("main", {}).get("feels_like"),
        "humidity": data.get("main", {}).get("humidity"),
        "pressure": data.get("main", {}).get("pressure"),
        "description": data.get("weather", [{}])[0].get("description"),
        "wind_speed": data.get("wind", {}).get("speed"),
        "wind_direction": data.get("wind", {}).get("deg"),
        "visibility": data.get("visibility"),
        "units": units,
        "raw": data,
    }


@register_node("openweathermap.get_forecast")
async def get_forecast(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Fetch 5-day / 3-hour weather forecast.

    Config / input keys:
      - city / lat+lon / zip (required) : Location selector.
      - units (str)                     : metric | imperial | standard. Default metric.
      - lang (str)                      : Language code. Default en.
      - cnt (int)                       : Number of timestamps (max 40). Default 40.
    """
    api_key = await _get_api_key(credential_id, db)
    units = config.get("units") or input_data.get("units", "metric")
    lang = config.get("lang") or input_data.get("lang", "en")
    cnt = min(int(config.get("cnt") or input_data.get("cnt", 40)), 40)

    params = _location_params(config, input_data)
    params.update({"appid": api_key, "units": units, "lang": lang, "cnt": cnt})

    log.info("openweathermap.get_forecast", params={k: v for k, v in params.items() if k != "appid"})
    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=20.0) as client:
        r = await client.get("forecast", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "city": data.get("city", {}).get("name"),
        "country": data.get("city", {}).get("country"),
        "forecast_count": len(data.get("list", [])),
        "forecast": data.get("list", []),
        "units": units,
        "raw": data,
    }


@register_node("openweathermap.get_air_quality")
async def get_air_quality(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Fetch air pollution / quality index for coordinates.

    Config / input keys:
      - lat (float, required) : Latitude.
      - lon (float, required) : Longitude.

    Returns AQI (1=Good … 5=Very Poor) and component concentrations.
    """
    api_key = await _get_api_key(credential_id, db)
    lat = config.get("lat") or input_data.get("lat")
    lon = config.get("lon") or input_data.get("lon")
    if lat is None or lon is None:
        raise ValueError("openweathermap.get_air_quality requires 'lat' and 'lon'")

    params = {"lat": lat, "lon": lon, "appid": api_key}

    log.info("openweathermap.get_air_quality", lat=lat, lon=lon)
    async with httpx.AsyncClient(base_url="https://api.openweathermap.org/data/2.5/", timeout=20.0) as client:
        r = await client.get("air_pollution", params=params)
        _raise_for_status(r)
        data = r.json()

    items = data.get("list", [{}])
    first = items[0] if items else {}
    aqi = first.get("main", {}).get("aqi")
    components = first.get("components", {})

    aqi_labels = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}

    return {
        "lat": lat,
        "lon": lon,
        "aqi": aqi,
        "aqi_label": aqi_labels.get(aqi, "Unknown"),
        "components": components,
        "raw": data,
    }
