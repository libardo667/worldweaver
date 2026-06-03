"""Real local weather for a familiar (Major 50).

Grounds the familiar in the keeper's actual sky: geolocate by IP (no key), then
pull current conditions from Open-Meteo (free, no key). The result is a short
phrase like ``"light rain, 52°F"`` — fed into grounding, where perception already
turns words like rain/fog/snow/wind into vigilance, so she *feels* the weather,
and the pulse prompt mentions it.

Everything is cached (geolocation once; conditions for ~10 min) and fails soft to
an empty string, so a familiar with no network simply has a blank sky rather than
a stuck tick. Overridable by env:

    WW_FAMILIAR_WEATHER="cold fog, 49°F"   # hard-code, skip the network entirely
    WW_FAMILIAR_LAT=37.77 WW_FAMILIAR_LON=-122.42   # skip IP geolocation
"""

from __future__ import annotations

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

# WMO weather codes (Open-Meteo). Phrasings keep the words perception keys on
# (rain, fog, snow, drizzle, thunder, storm) so adverse weather raises vigilance.
_WMO = {
    0: "clear sky",
    1: "mostly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "freezing fog",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    56: "freezing drizzle",
    57: "freezing drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    66: "freezing rain",
    67: "freezing rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    77: "snow grains",
    80: "rain showers",
    81: "rain showers",
    82: "heavy rain showers",
    85: "snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "thunderstorm with hail",
}


class WeatherProvider:
    """A cached, fail-soft source of the keeper's real local weather."""

    def __init__(self, *, refresh_seconds: float = 600.0, timeout: float = 4.0) -> None:
        self._refresh = refresh_seconds
        self._timeout = timeout
        self._cached = ""
        self._fetched_at = 0.0
        self._latlon: tuple[float, float] | None = None
        self._fixed = str(os.environ.get("WW_FAMILIAR_WEATHER", "")).strip()

    def __call__(self) -> str:
        if self._fixed:
            return self._fixed
        now = time.monotonic()
        if self._cached and (now - self._fetched_at) < self._refresh:
            return self._cached
        try:
            self._cached = self._fetch()
        except Exception as exc:  # network/geo failures → blank sky, never block
            logger.debug("[familiar:weather] fetch failed: %s", exc)
        self._fetched_at = now
        return self._cached

    def _coords(self) -> tuple[float, float] | None:
        if self._latlon is not None:
            return self._latlon
        lat = os.environ.get("WW_FAMILIAR_LAT", "").strip()
        lon = os.environ.get("WW_FAMILIAR_LON", "").strip()
        if lat and lon:
            self._latlon = (float(lat), float(lon))
            return self._latlon
        # IP geolocation (no key). The keeper's own machine looking up its own sky.
        resp = httpx.get("http://ip-api.com/json/?fields=lat,lon,city", timeout=self._timeout)
        data = resp.json()
        if data.get("lat") is not None and data.get("lon") is not None:
            self._latlon = (float(data["lat"]), float(data["lon"]))
            logger.info("[familiar:weather] grounded near %s", data.get("city") or "?")
        return self._latlon

    def _fetch(self) -> str:
        coords = self._coords()
        if coords is None:
            return self._cached
        lat, lon = coords
        resp = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current": "temperature_2m,weather_code,wind_speed_10m", "temperature_unit": "fahrenheit", "wind_speed_unit": "mph"},
            timeout=self._timeout,
        )
        cur = resp.json().get("current") or {}
        desc = _WMO.get(int(cur.get("weather_code", -1)), "")
        temp = cur.get("temperature_2m")
        wind = cur.get("wind_speed_10m")
        parts = [p for p in (desc, (f"{round(float(temp))}°F" if temp is not None else "")) if p]
        if wind is not None and float(wind) >= 18:
            parts.append(f"{round(float(wind))} mph wind")
        return ", ".join(parts)
