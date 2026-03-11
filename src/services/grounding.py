"""
grounding.py — Real-world grounding utilities.

Derives time, season, and weather from authoritative external sources rather
than mutable session state.  These values flow INTO the narrator as read-only
context; the LLM cannot write back to them.

Grounded facts:
    time_of_day   — derived from SF wall-clock time
    season        — derived from calendar month (SF timezone)
    weather       — Open-Meteo current conditions for SF (cached 15 min)
    temperature   — Open-Meteo current temperature in °F (cached 15 min)

Non-grounded (narrative state, LLM-mutable):
    danger_level, noise_level, lighting, air_quality
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

SF_TZ = ZoneInfo("America/Los_Angeles")

# SF coordinates (city centre)
_SF_LAT = 37.7749
_SF_LON = -122.4194

# Open-Meteo weather cache — avoids a live HTTP call on every narrator turn
_weather_cache: dict[str, Any] = {}
_weather_cache_ts: float = 0.0
_WEATHER_CACHE_TTL = 900  # seconds (15 minutes)

# WMO weather code → human-readable condition
_WMO_CONDITIONS: dict[int, str] = {
    0: "clear",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "freezing fog",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    80: "rain showers",
    81: "rain showers",
    82: "heavy rain showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "thunderstorm with heavy hail",
}


def _sf_now() -> datetime:
    return datetime.now(SF_TZ)


def _fetch_sf_weather() -> dict[str, Any]:
    """Fetch current SF weather from Open-Meteo (free, no API key)."""
    import urllib.request

    url = f"https://api.open-meteo.com/v1/forecast" f"?latitude={_SF_LAT}&longitude={_SF_LON}" f"&current=temperature_2m,weather_code,wind_speed_10m" f"&temperature_unit=fahrenheit" f"&wind_speed_unit=mph" f"&timezone=America%2FLos_Angeles"
    import json

    with urllib.request.urlopen(url, timeout=5) as resp:
        data = json.loads(resp.read())
    current = data.get("current", {})
    code = int(current.get("weather_code", 0))
    temp_f = current.get("temperature_2m")
    wind_mph = current.get("wind_speed_10m")

    condition = _WMO_CONDITIONS.get(code, "partly cloudy")
    temp_str = f"{round(temp_f)}°F" if temp_f is not None else None
    wind_str = f"{round(wind_mph)} mph winds" if wind_mph and wind_mph > 10 else None

    description_parts = [condition]
    if temp_str:
        description_parts.append(temp_str)
    if wind_str:
        description_parts.append(wind_str)

    return {
        "condition": condition,
        "temperature_f": round(temp_f) if temp_f is not None else None,
        "wind_mph": round(wind_mph) if wind_mph is not None else None,
        "wmo_code": code,
        "description": ", ".join(description_parts),
    }


def get_sf_weather() -> dict[str, Any]:
    """Return current SF weather, cached for 15 minutes.  Never raises."""
    global _weather_cache, _weather_cache_ts

    now_ts = time.monotonic()
    if _weather_cache and (now_ts - _weather_cache_ts) < _WEATHER_CACHE_TTL:
        return _weather_cache

    try:
        _weather_cache = _fetch_sf_weather()
        _weather_cache_ts = now_ts
    except Exception as exc:
        logger.warning("grounding: weather fetch failed (%s) — using cached/default", exc)
        if not _weather_cache:
            # First-call failure: return a safe default (SF is often foggy/mild)
            _weather_cache = {
                "condition": "partly cloudy",
                "temperature_f": 60,
                "wind_mph": None,
                "wmo_code": 2,
                "description": "partly cloudy, 60°F",
            }

    return _weather_cache


def get_sf_time_context() -> dict:
    """Return current SF time as narrator-ready grounding context."""
    now = _sf_now()
    hour = now.hour
    minute = now.minute
    month = now.month
    day = now.day

    # Derive time-of-day bucket
    if 5 <= hour < 12:
        time_of_day = "morning"
    elif 12 <= hour < 17:
        time_of_day = "afternoon"
    elif 17 <= hour < 21:
        time_of_day = "evening"
    else:
        time_of_day = "night"

    # Derive season from calendar month (Northern Hemisphere)
    if month in (12, 1, 2):
        season = "winter"
    elif month in (3, 4, 5):
        season = "spring"
    elif month in (6, 7, 8):
        season = "summer"
    else:
        season = "autumn"

    # Human-readable datetime string — portable across OS
    hour_12 = hour % 12 or 12
    ampm = "AM" if hour < 12 else "PM"
    month_name = now.strftime("%B")
    day_name = now.strftime("%A")
    datetime_str = f"{day_name}, {month_name} {day} at {hour_12}:{minute:02d} {ampm}"

    weather = get_sf_weather()

    return {
        "datetime_str": datetime_str,  # "Wednesday, March 11 at 2:34 PM"
        "day_of_week": day_name,  # "Wednesday"
        "time_of_day": time_of_day,  # "afternoon"
        "season": season,  # "spring"
        "hour": hour,  # 14
        "month": month,  # 3
        "weather": weather["condition"],  # "foggy"
        "temperature_f": weather["temperature_f"],  # 57
        "weather_description": weather["description"],  # "foggy, 57°F"
    }
