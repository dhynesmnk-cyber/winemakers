"""geocode.py — Nominatim over raw httpx, disk-cached. Gate 5.

TRD.md §7.6 and UX.md §1.5 row 10.

── This module never blocks a publish ────────────────────────────────────────

Null coordinates are a first-class outcome (SCHEMA.md §2). A label-only producer
with no cellar door has nowhere to put a pin and publishes normally, so every
failure path here returns `(None, None)` and logs a warning. Nothing in this
file raises into the pipeline.

── Nominatim's usage policy is a condition of use, not a suggestion ──────────

One request per second, absolute, and a User-Agent that identifies the
application with a contact address. Requests without one get blocked, and a
blocked geocoder is quiet: every new producer simply publishes with null
coordinates, which the schema allows, so the failure is easy to miss for weeks.
The rate limit is enforced here rather than trusted to the serial queue, because
the queue's serialisation is about politeness to producer websites and could
reasonably change; this cannot.

Results are cached to disk so an address is geocoded once, ever. The cache is
keyed on the normalised query string and lives in gitignored `temp_data/`.
"""

from __future__ import annotations

import json
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import (  # noqa: E402
    AU_LATITUDE_BOUNDS,
    AU_LONGITUDE_BOUNDS,
    GEOCODE_CACHE_PATH,
    GEOCODER,
    GEOCODER_USER_AGENT,
    HTTP_TIMEOUT_SECONDS,
)

Logger = Callable[[str, str], None]


def _null_log(level: str, message: str) -> None:
    pass


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

#: Nominatim's published policy. Not tunable.
MIN_INTERVAL_SECONDS = 1.0

_lock = threading.Lock()
_last_call = 0.0

_WHITESPACE = re.compile(r"\s+")


def _cache_key(query: str) -> str:
    return _WHITESPACE.sub(" ", query.strip().lower())


def _load_cache() -> dict[str, Any]:
    if not GEOCODE_CACHE_PATH.is_file():
        return {}
    try:
        data = json.loads(GEOCODE_CACHE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        # A corrupt cache is disposable. Losing it costs one request per address.
        return {}


def _save_cache(cache: dict[str, Any]) -> None:
    GEOCODE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = GEOCODE_CACHE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(GEOCODE_CACHE_PATH)


def build_query(location: dict[str, Any] | None) -> str:
    """The address string to geocode, or '' when there is nothing to look up.

    A bare suburb and state is worth geocoding; a bare state is not, and would
    return the centroid of South Australia as though it were a cellar door.
    """
    location = location or {}
    address = str(location.get("address") or "").strip()
    suburb = str(location.get("suburb") or "").strip()
    state = str(location.get("state") or "").strip()

    if not address and not suburb:
        return ""

    parts = [part for part in (address, suburb, state) if part]
    return ", ".join(parts) + ", Australia"


def _within_australia(lat: float, lon: float) -> bool:
    return (
        AU_LATITUDE_BOUNDS[0] <= lat <= AU_LATITUDE_BOUNDS[1]
        and AU_LONGITUDE_BOUNDS[0] <= lon <= AU_LONGITUDE_BOUNDS[1]
    )


def _throttle() -> None:
    global _last_call
    with _lock:
        wait = MIN_INTERVAL_SECONDS - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


def geocode(
    location: dict[str, Any] | None,
    *,
    log: Logger = _null_log,
    use_cache: bool = True,
) -> tuple[float | None, float | None]:
    """`(latitude, longitude)`, or `(None, None)`. Never raises."""
    query = build_query(location)
    if not query:
        log("warn", "geocode failed, publishing without a map pin (no address to geocode)")
        return None, None

    if GEOCODER != "nominatim":
        log("warn", f"geocode skipped, publishing without a map pin (GEOCODER={GEOCODER!r})")
        return None, None

    key = _cache_key(query)
    cache = _load_cache() if use_cache else {}
    if key in cache:
        hit = cache[key]
        if hit is None:
            log("warn", f"geocode failed, publishing without a map pin (cached miss: {query})")
            return None, None
        log("info", f"geocoding {query}  cached, {hit['lat']}, {hit['lon']}")
        return hit["lat"], hit["lon"]

    try:
        import httpx

        _throttle()
        with httpx.Client(
            headers={"User-Agent": GEOCODER_USER_AGENT},
            timeout=HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            response = client.get(
                NOMINATIM_URL,
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": 1,
                    "countrycodes": "au",
                },
            )
        if response.status_code != 200:
            log(
                "warn",
                f"geocode failed, publishing without a map pin "
                f"(HTTP {response.status_code})",
            )
            return None, None
        results = response.json()
    except Exception as exc:
        log(
            "warn",
            f"geocode failed, publishing without a map pin ({type(exc).__name__}: {exc})",
        )
        return None, None

    if not isinstance(results, list) or not results:
        cache[key] = None
        if use_cache:
            _save_cache(cache)
        log("warn", f"geocode failed, publishing without a map pin (no match for {query})")
        return None, None

    try:
        lat = round(float(results[0]["lat"]), 6)
        lon = round(float(results[0]["lon"]), 6)
    except (KeyError, TypeError, ValueError):
        log("warn", "geocode failed, publishing without a map pin (unreadable response)")
        return None, None

    if not _within_australia(lat, lon):
        # A pin outside Australia is wrong rather than imprecise, and the zod
        # bounds would reject it at build time anyway.
        log(
            "warn",
            f"geocode failed, publishing without a map pin "
            f"(result {lat}, {lon} is outside Australia)",
        )
        return None, None

    cache[key] = {"lat": lat, "lon": lon}
    if use_cache:
        _save_cache(cache)
    log("info", f"geocoding {query}  ok, {lat}, {lon}")
    return lat, lon
