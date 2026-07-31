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

Important API quirk this module works around: a station-wide departure_mon
call returns a capped number of events (~40, trains and buses combined,
shared across every platform). At a busy multi-platform station, a
high-frequency platform can consume that whole budget and silently push
a quieter platform's events out of the response entirely -- confirmed
empirically at Auburn, where platforms 1/2 (frequent) squeezed platforms
3/4 (less frequent) out of both a near-term and a 90-minutes-back call.
The fix is to discover the station's platforms once (cached for a day,
since a station's physical platforms don't change), then query each
platform individually (`nameKey_dm=$USEPOINT$`) so every platform gets
its own dedicated event budget.
"""
import logging
import re
from datetime import datetime
from datetime import timedelta
from datetime import timezone as dt_timezone

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
RECENT_LOOKBACK_MINUTES = 90  # how far back to search for "recent" trains
RECENT_COUNT = 5
UPCOMING_COUNT = 10  # a platform's own dedicated event budget can span 12+ hours; cap the display
LAST_TRAIN_ANCHOR_HOUR = 21  # start the end-of-day walk from 9pm Sydney time
LAST_TRAIN_MAX_STEPS = 5  # safety cap on the per-platform walk-forward loop
OVERNIGHT_GAP_MINUTES = 45  # a gap at least this long marks the daily service break
LAST_TRAIN_WALK_HOURS = 10  # how far past the anchor to walk looking for that gap
PLATFORM_DISCOVERY_HOURS = (7, 12, 17, 21)  # spread across the day to catch every platform
TRIP_CACHE_SECONDS = 60
MODE_NAMES = {1: "Train", 4: "Light Rail", 5: "Bus", 7: "Coach", 9: "Ferry", 11: "School Bus", 99: "Walk", 100: "Walk"}
SEARCH_CACHE_SECONDS = 300
DEPARTURES_CACHE_SECONDS = 60
PLATFORM_LIST_CACHE_SECONDS = 86400
LAST_TRAIN_CACHE_SECONDS = 1800
PLATFORM_RE = re.compile(r"Platform\s+[\w-]+", re.IGNORECASE)
PLATFORM_SUFFIX_RE = re.compile(r",?\s*Platform\s+[\w-]+\s*$", re.IGNORECASE)


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


def _search_station_locations(query):
    """[{id, name, is_best, match_quality}], best match first. stop_finder
    also returns bus stops/streets/addresses for the same search text, so
    this keeps only type=='stop' locations whose modes include train."""
    query = (query or "").strip()
    if len(query) < 2:
        return []

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
        results.append({
            "id": loc["id"], "name": loc.get("disassembledName") or loc.get("name"),
            "is_best": bool(loc.get("isBest")), "match_quality": loc.get("matchQuality", 0),
        })
    results.sort(key=lambda r: -r["match_quality"])
    return results


def search_stations(query):
    """[{id, name}] of train stations matching the search text, name order."""
    cache_key = f"trains:search:{(query or '').strip().lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    results = sorted(
        ({"id": r["id"], "name": r["name"]} for r in _search_station_locations(query)),
        key=lambda r: r["name"],
    )
    cache.set(cache_key, results, SEARCH_CACHE_SECONDS)
    return results


def resolve_station(query):
    """The single best-match station for `query`, or None if the search is
    empty, has no match, or is ambiguous (no clear best result) -- callers
    should fall back to showing the candidate list in that case."""
    results = _search_station_locations(query)
    if not results:
        return None
    best = results[0]
    if best["is_best"]:
        return {"id": best["id"], "name": best["name"]}
    if len(results) == 1:
        return {"id": best["id"], "name": best["name"]}
    return None


def _sydney_now():
    now = timezone.now()
    return now.astimezone(SYDNEY_TZ) if SYDNEY_TZ else now


def _parse_time(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _station_only_name(name):
    """Strips a trailing ', Platform N' so a leg's origin/destination name
    doesn't duplicate the separately-shown platform field."""
    return PLATFORM_SUFFIX_RE.sub("", name or "").strip()


def _platform_label(location, station_name):
    properties = location.get("properties") or {}
    if properties.get("platformName"):
        return properties["platformName"]
    name = location.get("disassembledName") or location.get("name") or ""
    match = PLATFORM_RE.search(name)
    if match:
        return match.group(0)
    if station_name and name.startswith(station_name):
        name = name[len(station_name):].strip(", ")
    return name or "Platform (unspecified)"


def _fetch_train_events(stop_id, anchor_time, station_name=None, use_point=False):
    """One departure_mon call anchored at `anchor_time` (a Sydney-local
    datetime), filtered to trains only. `use_point=True` scopes the query
    to a single platform ID (stop_id must then be a platform location id,
    not a station id), giving that platform its own dedicated event
    budget instead of sharing the station-wide one. Returns item dicts
    carrying an absolute `departure_dt` (aware UTC) alongside the
    display-ready fields."""
    params = {
        "outputFormat": "rapidJSON",
        "coordOutputFormat": "EPSG:4326",
        "mode": "direct",
        "type_dm": "stop",
        "name_dm": stop_id,
        "depArrMacro": "dep",
        "itdDate": anchor_time.strftime("%Y%m%d"),
        "itdTime": anchor_time.strftime("%H%M"),
        "TfNSWDM": "true",
    }
    if use_point:
        params["nameKey_dm"] = "$USEPOINT$"
    data = _get("departure_mon", params)

    now_utc = timezone.now()
    events = []
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
        local_dt = effective.astimezone(SYDNEY_TZ) if SYDNEY_TZ else effective
        events.append({
            "platform": platform_name,
            "platform_id": location.get("id"),
            "line": transportation.get("number") or "Train",
            "destination": (transportation.get("destination") or {}).get("name", "—"),
            "planned": planned,
            "estimated": estimated,
            "is_realtime": bool(event.get("isRealtimeControlled")),
            "minutes": minutes,
            "minutes_ago": -minutes,
            "departure_dt": effective,
            "local_time": local_dt.strftime("%H:%M"),
            "is_next_day": local_dt.date() != _sydney_now().date(),
        })
    return events


def _discover_platforms(stop_id, station_name=None):
    """[{platform, platform_id}] -- every train platform this station has,
    found by sampling the station-wide feed at several times of day and
    taking the union of platforms seen (a single sample can miss a
    quieter platform, see module docstring). Cached for a day since a
    station's physical platforms essentially never change."""
    cache_key = f"trains:platforms:{stop_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    today = _sydney_now().replace(minute=0, second=0, microsecond=0)
    found = {}
    for hour in PLATFORM_DISCOVERY_HOURS:
        anchor = today.replace(hour=hour)
        events = _fetch_train_events(stop_id, anchor, station_name)
        for item in events:
            if item["platform_id"]:
                found.setdefault(item["platform_id"], item["platform"])

    platforms = [{"platform": name, "platform_id": pid} for pid, name in found.items()]
    platforms.sort(key=lambda p: p["platform"])
    cache.set(cache_key, platforms, PLATFORM_LIST_CACHE_SECONDS)
    return platforms


def get_departure_board(stop_id, station_name=None):
    """{"platforms": [{"platform": str, "platform_id": str, "recent": [event...], "upcoming": [event...]}], "fetched_at": datetime}
    `recent` is up to RECENT_COUNT most-recently-departed trains (closest
    first). `upcoming` is every returned not-yet-departed train (soonest
    first). Queries each discovered platform individually so a quiet
    platform can't get crowded out by a busy one sharing the same
    station-wide response budget."""
    cache_key = f"trains:departures:{stop_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    now_syd = _sydney_now()
    platforms_out = []
    for platform in _discover_platforms(stop_id, station_name):
        pid = platform["platform_id"]
        upcoming_events = [
            e for e in _fetch_train_events(pid, now_syd, station_name, use_point=True) if e["minutes"] >= 0
        ]
        recent_events = [
            e for e in _fetch_train_events(pid, now_syd - timedelta(minutes=RECENT_LOOKBACK_MINUTES), station_name, use_point=True)
            if e["minutes"] < 0
        ]
        upcoming_events.sort(key=lambda i: i["minutes"])
        recent_events.sort(key=lambda i: i["minutes"], reverse=True)  # closest-to-now first
        platforms_out.append({
            "platform": platform["platform"],
            "platform_id": pid,
            "recent": recent_events[:RECENT_COUNT],
            "upcoming": upcoming_events[:UPCOMING_COUNT],
        })

    result = {"platforms": sorted(platforms_out, key=lambda b: b["platform"]), "fetched_at": timezone.now()}
    cache.set(cache_key, result, DEPARTURES_CACHE_SECONDS)
    return result


def _last_train_for_platform(platform_id, station_name):
    """Walks a single platform's own departure_mon feed forward from a
    fixed evening anchor until it finds a gap between consecutive
    departures of at least OVERNIGHT_GAP_MINUTES -- that gap is the daily
    service break, and the train right before it is "last train". Many
    Sydney lines run close to 24 hours, so just taking "the latest event
    seen" would walk straight into tomorrow's normal timetable instead of
    stopping at a real overnight break."""
    anchor = _sydney_now().replace(hour=LAST_TRAIN_ANCHOR_HOUR, minute=0, second=0, microsecond=0)
    walk_until = anchor + timedelta(hours=LAST_TRAIN_WALK_HOURS)
    walk_until_utc = walk_until.astimezone(dt_timezone.utc) if SYDNEY_TZ else walk_until
    cursor = anchor
    by_time = {}
    for _ in range(LAST_TRAIN_MAX_STEPS):
        events = _fetch_train_events(platform_id, cursor, station_name, use_point=True)
        events = [e for e in events if e["departure_dt"] <= walk_until_utc]
        if not events:
            break
        for item in events:
            by_time[item["departure_dt"]] = item  # dedupe; overlapping calls repeat events
        round_max = max(item["departure_dt"] for item in events)
        next_cursor = (round_max.astimezone(SYDNEY_TZ) if SYDNEY_TZ else round_max) + timedelta(minutes=1)
        if next_cursor <= cursor or next_cursor >= walk_until:
            break
        cursor = next_cursor

    if not by_time:
        return None
    ordered = [by_time[t] for t in sorted(by_time)]
    best_gap = timedelta(0)
    last_before_gap = ordered[-1]
    for earlier, later in zip(ordered, ordered[1:]):
        gap = later["departure_dt"] - earlier["departure_dt"]
        if gap > best_gap:
            best_gap = gap
            last_before_gap = earlier
    gap_minutes = int(best_gap.total_seconds() / 60)
    return {**last_before_gap, "gap_minutes": gap_minutes if gap_minutes >= OVERNIGHT_GAP_MINUTES else None}


def get_last_trains_today(stop_id, station_name=None):
    """{platform_name: event} -- the last scheduled train before the
    overnight service gap, per platform. `gap_minutes` on the result is
    None (show as uncertain) if no clear gap turned up within the walked
    window (~9pm to ~7am)."""
    cache_key = f"trains:last:{stop_id}:{_sydney_now().strftime('%Y%m%d')}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = {}
    for platform in _discover_platforms(stop_id, station_name):
        found = _last_train_for_platform(platform["platform_id"], station_name)
        if found:
            result[platform["platform"]] = found

    cache.set(cache_key, result, LAST_TRAIN_CACHE_SECONDS)
    return result


def get_trip(origin_id, destination_id, when=None, arrive_by=False):
    """[{depart, arrive, duration_minutes, transfers, legs: [...]}], soonest
    first (or, for arrive_by, closest-to-arrival first -- matches the
    order the API already returns). Each leg has: mode_name, line,
    headsign, origin_name, origin_platform, destination_name,
    destination_platform, depart, depart_is_realtime, arrive,
    arrive_is_realtime, duration_minutes."""
    when = when or _sydney_now()
    cache_key = f"trains:trip:{origin_id}:{destination_id}:{when.strftime('%Y%m%d%H%M')}:{arrive_by}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = _get("trip", {
        "outputFormat": "rapidJSON",
        "coordOutputFormat": "EPSG:4326",
        "depArrMacro": "arr" if arrive_by else "dep",
        "itdDate": when.strftime("%Y%m%d"),
        "itdTime": when.strftime("%H%M"),
        "type_origin": "stop",
        "name_origin": origin_id,
        "type_destination": "stop",
        "name_destination": destination_id,
        "TfNSWTR": "true",
    })

    journeys = []
    for journey in data.get("journeys", []):
        legs_out = []
        for leg in journey.get("legs", []):
            transportation = leg.get("transportation") or {}
            mode_class = (transportation.get("product") or {}).get("class")
            origin = leg.get("origin") or {}
            destination = leg.get("destination") or {}

            dep_planned = _parse_time(origin.get("departureTimePlanned"))
            dep_estimated = _parse_time(origin.get("departureTimeEstimated"))
            arr_planned = _parse_time(destination.get("arrivalTimePlanned"))
            arr_estimated = _parse_time(destination.get("arrivalTimeEstimated"))
            depart = dep_estimated or dep_planned
            arrive = arr_estimated or arr_planned
            if depart is None or arrive is None:
                continue

            duration_seconds = leg.get("duration")
            legs_out.append({
                "mode_class": mode_class,
                "mode_name": MODE_NAMES.get(mode_class, (transportation.get("product") or {}).get("name", "")),
                "line": transportation.get("number") or "",
                "headsign": (transportation.get("destination") or {}).get("name", ""),
                "origin_name": _station_only_name(origin.get("disassembledName") or origin.get("name")),
                "origin_platform": (origin.get("properties") or {}).get("platformName", "") if mode_class == TRAIN_MODE else "",
                "destination_name": _station_only_name(destination.get("disassembledName") or destination.get("name")),
                "destination_platform": (destination.get("properties") or {}).get("platformName", "") if mode_class == TRAIN_MODE else "",
                "depart": depart,
                "depart_is_realtime": dep_estimated is not None,
                "arrive": arrive,
                "arrive_is_realtime": arr_estimated is not None,
                "duration_minutes": round(duration_seconds / 60) if duration_seconds else None,
            })
        if not legs_out:
            continue

        total_depart = legs_out[0]["depart"]
        total_arrive = legs_out[-1]["arrive"]
        journeys.append({
            "depart": total_depart,
            "arrive": total_arrive,
            "duration_minutes": round((total_arrive - total_depart).total_seconds() / 60),
            "transfers": journey.get("interchanges", max(0, len(legs_out) - 1)),
            "legs": legs_out,
        })

    cache.set(cache_key, journeys, TRIP_CACHE_SECONDS)
    return journeys
