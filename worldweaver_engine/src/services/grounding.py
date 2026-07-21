# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Read-only clock and weather context for the shard's configured city.

Real city packs use their own timezone and Open-Meteo coordinates. Fictional
packs use their declared timezone and authored conditions; they never borrow a
real city's weather merely because their schematic needs coordinates.

Grounded facts:
    time_of_day   — derived from the city pack's local wall-clock time
    season        — derived from the local calendar month
    weather       — city-specific live or authored conditions
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

# SF coordinates (city centre)
_SF_LAT = 37.7749
_SF_LON = -122.4194

# Open-Meteo weather cache — avoids a live HTTP call on every grounding read
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


def _fetch_open_meteo_weather(
    latitude: float, longitude: float, timezone_name: str
) -> dict[str, Any]:
    """Fetch current weather from Open-Meteo (free, no API key)."""
    import urllib.request
    from urllib.parse import urlencode

    params = urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,weather_code,wind_speed_10m",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "timezone": timezone_name,
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
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


def _fetch_sf_weather() -> dict[str, Any]:
    """Backward-compatible San Francisco weather fetch."""
    return _fetch_open_meteo_weather(_SF_LAT, _SF_LON, "America/Los_Angeles")


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
        logger.warning(
            "grounding: weather fetch failed (%s) — using cached/default", exc
        )
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


_city_weather_cache: dict[str, dict[str, Any]] = {}
_city_weather_cache_ts: dict[str, float] = {}


def _city_config(city_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    from .city_pack_service import get_pack

    pack = get_pack(city_id) or {}
    return dict(pack.get("manifest") or {}), dict(pack.get("weather_config") or {})


def get_city_weather(city_id: str) -> dict[str, Any]:
    """Return honest weather for a real or fictional city pack. Never raises."""
    manifest, weather_config = _city_config(city_id)
    fictional = bool(manifest.get("fictional", weather_config.get("fictional", False)))
    if fictional:
        description = str(
            weather_config.get("default_conditions")
            or "Local conditions are not specified."
        ).strip()
        return {
            "condition": description,
            "temperature_f": None,
            "wind_mph": None,
            "wmo_code": None,
            "description": description,
        }

    latitude = weather_config.get("open_meteo_lat")
    longitude = weather_config.get("open_meteo_lon")
    timezone_name = str(weather_config.get("timezone") or "UTC")
    if latitude is None or longitude is None:
        return (
            get_sf_weather()
            if city_id == "san_francisco"
            else {
                "condition": "conditions unavailable",
                "temperature_f": None,
                "wind_mph": None,
                "wmo_code": None,
                "description": "Current conditions are unavailable.",
            }
        )

    now_ts = time.monotonic()
    cached = _city_weather_cache.get(city_id)
    if (
        cached
        and now_ts - _city_weather_cache_ts.get(city_id, 0.0) < _WEATHER_CACHE_TTL
    ):
        return cached
    try:
        fresh = _fetch_open_meteo_weather(
            float(latitude), float(longitude), timezone_name
        )
        _city_weather_cache[city_id] = fresh
        _city_weather_cache_ts[city_id] = now_ts
        return fresh
    except Exception as exc:
        logger.warning(
            "grounding: weather fetch failed for %s (%s) — using cached/default",
            city_id,
            exc,
        )
        if cached:
            return cached
        return {
            "condition": "conditions unavailable",
            "temperature_f": None,
            "wind_mph": None,
            "wmo_code": None,
            "description": "Current conditions are unavailable.",
        }


# ---------------------------------------------------------------------------
# SF news headlines — RSS-backed, 1-hour cache
# ---------------------------------------------------------------------------

# RSS feeds to try in order — first successful response wins.
_NEWS_FEEDS: list[str] = [
    "https://www.kqed.org/news/feed",  # KQED Bay Area
    "https://sfstandard.com/feed/",  # SF Standard
]

_news_cache: list[dict] = []
_news_cache_ts: float = 0.0
_NEWS_CACHE_TTL = 3600  # seconds (1 hour)


def _fetch_sf_news(max_items: int = 5) -> list[dict]:
    """Fetch recent SF/Bay Area headlines from RSS. Returns list of {title}."""
    import urllib.request
    import xml.etree.ElementTree as ET

    for feed_url in _NEWS_FEEDS:
        try:
            with urllib.request.urlopen(feed_url, timeout=6) as resp:
                data = resp.read()
            root = ET.fromstring(data)
            # Standard RSS 2.0: <channel><item><title>
            items: list[dict] = []
            for item in root.findall(".//item")[:max_items]:
                title = (item.findtext("title") or "").strip()
                if title:
                    items.append({"title": title})
            # Atom fallback: <entry><title>
            if not items:
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall("atom:entry", ns)[:max_items]:
                    title_el = entry.find("atom:title", ns)
                    title = (
                        (title_el.text or "").strip() if title_el is not None else ""
                    )
                    if title:
                        items.append({"title": title})
            if items:
                return items
        except Exception:
            continue
    return []


def get_sf_news(max_items: int = 5) -> list[dict]:
    """Return recent SF/Bay Area news headlines, cached for 1 hour. Never raises."""
    global _news_cache, _news_cache_ts

    now_ts = time.monotonic()
    if _news_cache and (now_ts - _news_cache_ts) < _NEWS_CACHE_TTL:
        return _news_cache

    try:
        fresh = _fetch_sf_news(max_items)
        if fresh:
            _news_cache = fresh
            _news_cache_ts = now_ts
    except Exception as exc:
        logger.warning("grounding: news fetch failed (%s) — using cached", exc)

    return _news_cache


def get_city_time_context(city_id: str, *, now: datetime | None = None) -> dict:
    """Return current local time and honest weather for one city pack."""
    manifest, weather_config = _city_config(city_id)
    timezone_name = str(weather_config.get("timezone") or "UTC")
    try:
        city_timezone = ZoneInfo(timezone_name)
    except Exception:
        city_timezone = ZoneInfo("UTC")
        timezone_name = "UTC"
    current = (
        now.astimezone(city_timezone)
        if now is not None
        else datetime.now(city_timezone)
    )
    hour = current.hour
    minute = current.minute
    month = current.month
    day = current.day

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
    month_name = current.strftime("%B")
    day_name = current.strftime("%A")
    datetime_str = f"{day_name}, {month_name} {day} at {hour_12}:{minute:02d} {ampm}"

    weather = get_city_weather(city_id)

    return {
        "city": str(
            manifest.get("city")
            or weather_config.get("city")
            or city_id.replace("_", " ").title()
        ),
        "city_id": city_id,
        "fictional": bool(
            manifest.get("fictional", weather_config.get("fictional", False))
        ),
        "timezone": timezone_name,
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


def get_sf_time_context() -> dict:
    """Backward-compatible San Francisco grounding entrypoint."""
    return get_city_time_context("san_francisco")
