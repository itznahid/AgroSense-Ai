"""
WeatherAPI.com helper — AgroSense
──────────────────────────────────
Fetches Temperature (°C), Humidity (%), and estimated monthly Rainfall (mm)
for the crop-recommendation ML model.

Rainfall strategy
  The ML model was trained on average monthly rainfall (dataset range 0–300 mm).
  WeatherAPI's current-day totalprecip_mm is 0.0 on most dry days, which would
  break predictions.  Fix: request N forecast days, sum precipitation across all
  returned days, then scale to a 30-day estimate.

  Free plan returns up to 3 days; paid plans return up to 14.
  We request 7 — the API silently caps at whatever the plan allows.

Endpoints used
  GET https://api.weatherapi.com/v1/forecast.json
      ?key=KEY&q=QUERY&days=7&aqi=no&alerts=no
"""

import re
import ssl
import json
import logging
import urllib.request
import urllib.parse
import urllib.error

from django.conf import settings

logger = logging.getLogger(__name__)

WEATHER_API_FORECAST = "https://api.weatherapi.com/v1/forecast.json"
TIMEOUT_SECONDS      = 12
FORECAST_DAYS        = 7   # API caps silently at plan limit (3 for free, 14 for paid)

# Bypass SSL verification for servers behind proxies that inject self-signed certs
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode    = ssl.CERT_NONE


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _api_key() -> str:
    key = getattr(settings, "WEATHER_API_KEY", "").strip()
    if not key or key == "YOUR_WEATHERAPI_KEY_HERE":
        raise ValueError("WEATHER_API_KEY is not configured in settings.py.")
    return key


def _fetch(query: str, source: str) -> dict:
    """
    One WeatherAPI call → current conditions + N-day forecast.
    Returns a normalised result dict or {"ok": False, "error": "..."}.
    """
    try:
        key = _api_key()
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "status": 500}

    params = urllib.parse.urlencode({
        "key":    key,
        "q":      query,
        "days":   FORECAST_DAYS,
        "aqi":    "no",
        "alerts": "no",
    })
    url = f"{WEATHER_API_FORECAST}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "AgroSense/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=_SSL_CTX) as resp:
            raw = resp.read()

    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read())
            msg  = body.get("error", {}).get("message", str(exc))
        except Exception:
            msg = str(exc)
        logger.warning("WeatherAPI HTTP %s for q=%r: %s", exc.code, query, msg)
        # 400 = bad location (client error), 401/403 = bad key (config error)
        status = 400 if exc.code == 400 else 500
        return {"ok": False, "error": f"WeatherAPI ({exc.code}): {msg}", "status": status}

    except urllib.error.URLError as exc:
        logger.warning("WeatherAPI URLError for q=%r: %s", query, exc.reason)
        return {"ok": False, "error": f"Cannot reach WeatherAPI: {exc.reason}", "status": 503}

    except Exception as exc:
        logger.exception("Unexpected weather fetch error for q=%r", query)
        return {"ok": False, "error": f"Unexpected error: {exc}", "status": 503}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "error": "Invalid JSON from WeatherAPI.", "status": 503}

    try:
        loc     = data["location"]
        current = data["current"]
        days    = data["forecast"]["forecastday"]   # 1–7 items depending on plan

        temperature = round(float(current["temp_c"]), 1)
        humidity    = int(current["humidity"])

        # Sum all returned forecast days and scale to 30-day monthly estimate
        forecast_precip  = sum(float(d["day"]["totalprecip_mm"]) for d in days)
        n_days           = len(days) or 1
        monthly_rainfall = round(forecast_precip * (30 / n_days), 1)
        # Clamp to training data range — allow 0 for genuinely arid regions
        monthly_rainfall = max(0.0, min(300.0, monthly_rainfall))

        location_label = ", ".join(filter(None, [
            loc.get("name"), loc.get("region"), loc.get("country"),
        ]))

        return {
            "ok":          True,
            "temperature": temperature,
            "humidity":    humidity,
            "rainfall":    monthly_rainfall,
            "location":    location_label,
            "condition":   current.get("condition", {}).get("text", ""),
            "icon":        current.get("condition", {}).get("icon", ""),
            "source":      source,
        }

    except (KeyError, IndexError, TypeError, ValueError) as exc:
        logger.error("WeatherAPI unexpected structure: %s | keys=%s", exc, list(data.keys()))
        return {"ok": False, "error": "Unexpected data structure from WeatherAPI.", "status": 503}


def _clean_city_variants(city: str) -> list:
    """
    Return progressively simpler query strings to try against WeatherAPI.
    Handles messy input like "ashulia. ,Dhaka" → ["ashulia, Dhaka", "ashulia", "Dhaka"]
    """
    cleaned = re.sub(r'[.;]+', '', city)
    cleaned = re.sub(r'\s*,\s*', ', ', cleaned).strip().strip(',').strip()

    candidates = [cleaned]
    parts = [p.strip() for p in cleaned.split(',') if p.strip()]
    if len(parts) > 1:
        candidates.extend(parts)

    seen, unique = set(), []
    for c in candidates:
        if c.lower() not in seen:
            seen.add(c.lower())
            unique.append(c)
    return unique


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def fetch_weather(city: str) -> dict:
    """
    Fetch by city name. Auto-retries with cleaned/simplified variants so
    messy input like 'ashulia. ,Dhaka' still resolves:
      try 1 → "ashulia, Dhaka"
      try 2 → "ashulia"
      try 3 → "Dhaka"  ← likely succeeds
    """
    if not city or not city.strip():
        return {"ok": False, "error": "No city name provided.", "status": 400}

    last = {"ok": False, "error": "City not found.", "status": 400}
    for candidate in _clean_city_variants(city):
        result = _fetch(candidate, source="city")
        if result.get("ok"):
            return result
        last = result
        logger.debug("City query %r failed: %s", candidate, result.get("error"))
    return last


def fetch_weather_by_coords(lat: float, lon: float) -> dict:
    """Fetch by GPS coordinates."""
    return _fetch(f"{lat},{lon}", source="gps")