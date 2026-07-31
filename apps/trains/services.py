"""Train Lookup: live wrapper around the Transport for NSW Open Data Trip
Planner APIs (stop_finder + departure_mon). No local persistence -- this
is a live lookup, backed by a short cache to avoid hammering the upstream
API on every page refresh.

Deliberately NOT supported: non-stopping/express trains passing through a
platform without stopping. departure_mon is a departure board -- it only
returns actual stop events, so a train that skips a station has no event
there at all. Getting that would need static GTFS timetables cross-
referenced with real-time vehicle positions, a much larger undertaking,
and was explicitly dropped as out of scope.
"""
import logging
import re
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

try:
    from zoneinfo import ZoneInfo
    SYDNEY_TZ = ZoneInfo("Australia/Sydney")
except ImportError:  # pragma: no cover
    SYDNEY_TZ = None

logger = logging.getLogger(__name__)

TRAIN_MODE = 1  # transportation.product.class value for trains
REQUEST_TIMEOUT_SECONDS = 8
LOOKBACK_MINUTES = 30
SEARCH_CACHE_SECONDS = 300
DEPARTURES_CACHE_SECONDS = 30
PLATFORM_RE = re.compile(r"Platform\s+[\w-]+", re.IGNORECASE)


class TrainApiError(Exception):
    """Any failure talking to the Transport for NSW API -- bad key,
    timeout, unexpected response shape. Callers show a friendly message
    instead of a 500."""


def _headers():
    if not settings.TFNSW_API_KEY:
        raise TrainApiError("No Transport for NSW API key is configured.")
    return {"Authorization": f"apikey {settings.TFNSW_API_KEY}"}


def _get(endpoint, params):
    url = settings.TFNSW_API_BASE + endpoint
    try:
        resp = requests.get(url, params=params, headers=_headers(), timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        logger.warning("TfNSW API request failed: %s", exc)
        raise TrainApiError("Could not reach the Transport for NSW service. Try again shortly.") from exc
    if resp.status_code == 401:
        raise TrainApiError("The Transport for NSW API key was rejected.")
    if resp.status_code == 429:
        raise TrainApiError("Too many requests to Transport for NSW right now. Try again in a moment.")
    if not resp.ok:
        logger.warning("TfNSW API returned %s: %s", resp.status_code, resp.text[:300])
        raise TrainApiError("The Transport for NSW service returned an error.")
    try:
        return resp.json()
    except ValueError as exc:
        raise TrainApiError("The Transport for NSW service returned an unexpected response.") from exc


def search_stations(query):
    """[{id, name}] of train stations matching the search text. stop_finder
    also returns bus stops/streets/addresses for the same text, so this
    keeps only type=='stop' locations whose modes include train."""
    query = (query or "").strip()
    if len(query) < 2:
        return []

    cache_key = f"trains:search:{query.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = _get("stop_finder", {
        "outputFormat": "rapidJSON",
        "type_sf": "any",
        "name_sf": query,
        "coordOutputFormat": "EPSG:4326",
        "TfNSWSF": "true",
        "odvSugMacro": 1,
    })
    results = []
    seen_ids = set()
    for loc in data.get("locations", []):
        if loc.get("type") != "stop":
            continue
        if TRAIN_MODE not in (loc.get("modes") or []):
            continue
        if loc["id"] in seen_ids:
            continue
        seen_ids.add(loc["id"])
        results.append({"id": loc["id"], "name": loc.get("disassembledName") or loc.get("name")})
    results.sort(key=lambda r: r["name"])
    cache.set(cache_key, results, SEARCH_CACHE_SECONDS)
    return results


def _sydney_now():
    now = timezone.now()
    return now.astimezone(SYDNEY_TZ) if SYDNEY_TZ else now


def _parse_time(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _platform_label(location, station_name):
    name = location.get("disassembledName") or location.get("name") or ""
    match = PLATFORM_RE.search(name)
    if match:
        return match.group(0)
    if station_name and name.startswith(station_name):
        name = name[len(station_name):].strip(", ")
    return name or "Platform (unspecified)"


def get_departure_board(stop_id, station_name=None, lookback_minutes=LOOKBACK_MINUTES):
    """{"platforms": [{"platform": str, "last_stopped": event|None, "upcoming": [event...]}], "fetched_at": datetime}
    An event dict has: line, destination, planned, estimated, is_realtime, minutes (negative = already departed)."""
    cache_key = f"trains:departures:{stop_id}:{lookback_minutes}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    query_time = _sydney_now() - timedelta(minutes=lookback_minutes)
    data = _get("departure_mon", {
        "outputFormat": "rapidJSON",
        "coordOutputFormat": "EPSG:4326",
        "mode": "direct",
        "type_dm": "stop",
        "name_dm": stop_id,
        "depArrMacro": "dep",
        "itdDate": query_time.strftime("%Y%m%d"),
        "itdTime": query_time.strftime("%H%M"),
        "TfNSWDM": "true",
    })

    now_utc = timezone.now()
    platforms = {}
    for event in data.get("stopEvents", []):
        transportation = event.get("transportation") or {}
        if (transportation.get("product") or {}).get("class") != TRAIN_MODE:
            continue  # a multi-mode stop's departure_mon can include buses too

        location = event.get("location") or {}
        platform_name = _platform_label(location, station_name)

        planned = _parse_time(event.get("departureTimePlanned"))
        estimated = _parse_time(event.get("departureTimeEstimated"))
        effective = estimated or planned
        if effective is None:
            continue

        minutes = round((effective - now_utc).total_seconds() / 60)
        item = {
            "line": transportation.get("number") or "Train",
            "destination": (transportation.get("destination") or {}).get("name", "—"),
            "planned": planned,
            "estimated": estimated,
            "is_realtime": bool(event.get("isRealtimeControlled")),
            "minutes": minutes,
            "minutes_ago": -minutes,  # display-ready positive value for "N min ago"
        }
        bucket = platforms.setdefault(platform_name, {"platform": platform_name, "last_stopped": None, "upcoming": []})
        if item["minutes"] < 0:
            if bucket["last_stopped"] is None or item["minutes"] > bucket["last_stopped"]["minutes"]:
                bucket["last_stopped"] = item
        else:
            bucket["upcoming"].append(item)

    for bucket in platforms.values():
        bucket["upcoming"].sort(key=lambda i: i["minutes"])

    result = {"platforms": sorted(platforms.values(), key=lambda b: b["platform"]), "fetched_at": now_utc}
    cache.set(cache_key, result, DEPARTURES_CACHE_SECONDS)
    return result
