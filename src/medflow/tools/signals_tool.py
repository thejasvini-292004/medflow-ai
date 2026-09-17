"""External environmental-signal tool.

Fetches current/near-term weather for the hospital's location (Open-Meteo, a
free keyless API) and derives a simple **respiratory-illness surge proxy** that
combines the calendar season with cold-temperature pressure. Weather and season
are well-known drivers of ED respiratory volume, so this gives the agent a
real-world external signal to reason about capacity ("cold snap + January =>
expect higher ED respiratory volume").

If the network is unavailable or SIGNAL_USE_LIVE_API=false, it falls back to a
deterministic seasonal estimate so the tool always returns something usable
(important for offline / air-gapped client demos).
"""
from __future__ import annotations

import datetime as _dt
import math

import requests
from langchain_core.tools import tool

from ..config import settings

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

_WEATHER_CODES = {
    0: "clear", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "rime fog", 51: "light drizzle", 61: "light rain",
    63: "rain", 65: "heavy rain", 71: "light snow", 73: "snow", 75: "heavy snow",
    80: "rain showers", 95: "thunderstorm",
}


def _season_component(month: int) -> float:
    """0..1 seasonal respiratory pressure, peaking in January."""
    return round(0.5 + 0.5 * math.cos(2 * math.pi * (month - 1) / 12.0), 3)


def _temp_component(temp_c: float | None) -> float:
    """0..1 cold-pressure: rises as temperature falls below ~15C."""
    if temp_c is None:
        return 0.5
    return round(min(1.0, max(0.0, (15.0 - temp_c) / 25.0)), 3)


def _band(score: float) -> str:
    if score >= 0.66:
        return "HIGH"
    if score >= 0.4:
        return "ELEVATED"
    return "LOW"


def _surge_index(month: int, temp_c: float | None) -> tuple[float, str]:
    score = 0.6 * _season_component(month) + 0.4 * _temp_component(temp_c)
    return round(score, 3), _band(score)


def _offline(reason: str) -> str:
    today = _dt.date.today()
    idx, band = _surge_index(today.month, None)
    return (
        f"[offline estimate — {reason}]\n"
        f"Date: {today.isoformat()} | Location: "
        f"{settings.signal_lat:.3f},{settings.signal_lon:.3f}\n"
        f"Respiratory surge proxy: {band} (index {idx}). "
        f"Estimate is seasonal only (no live weather). "
        f"Nov–Feb is peak respiratory season per OPS-IC-005."
    )


@tool("get_environmental_signal")
def get_environmental_signal() -> str:
    """Fetch current weather + a respiratory-illness surge proxy for the hospital
    region. Returns temperature, conditions, and a surge band (LOW / ELEVATED /
    HIGH) with a short interpretation. Use this when a question involves expected
    patient influx, respiratory demand, weather impact, or capacity planning for
    the days ahead.
    """
    if not settings.signal_use_live_api:
        return _offline("live API disabled via SIGNAL_USE_LIVE_API")

    try:
        resp = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": settings.signal_lat,
                "longitude": settings.signal_lon,
                "current": "temperature_2m,relative_humidity_2m,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min",
                "forecast_days": 3,
                "timezone": "auto",
            },
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        return _offline(f"network error: {type(e).__name__}")

    cur = data.get("current", {})
    temp = cur.get("temperature_2m")
    rh = cur.get("relative_humidity_2m")
    code = cur.get("weather_code")
    cond = _WEATHER_CODES.get(code, f"code {code}")
    month = _dt.date.today().month
    idx, band = _surge_index(month, temp)

    daily = data.get("daily", {})
    lows = daily.get("temperature_2m_min", [])
    upcoming_low = min(lows) if lows else None

    lines = [
        f"Location: {settings.signal_lat:.3f},{settings.signal_lon:.3f}",
        f"Current: {temp}C, {cond}, humidity {rh}%",
    ]
    if upcoming_low is not None:
        lines.append(f"3-day forecast low: {upcoming_low}C")
    lines.append(f"Respiratory surge proxy: {band} (index {idx}).")
    if band in ("ELEVATED", "HIGH"):
        lines.append(
            "Interpretation: elevated respiratory demand likely — per OPS-IC-005 "
            "consider pre-opening overflow capacity and reviewing isolation beds."
        )
    else:
        lines.append("Interpretation: baseline respiratory demand expected.")
    return "\n".join(lines)
