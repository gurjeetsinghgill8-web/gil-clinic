"""Travel time — "should I leave now?" for the departure alert.

Why this file exists
--------------------
The departure alert (Part D · E-03) used to say "ab niklo" based on the wait
alone. But a patient 25 minutes away was told to leave when 6 minutes remained,
turned up late, and lost their token — while a patient next door was told to
leave with 30 minutes to spare and stood outside in the sun.

The honest rule (enterprise blueprint F-09b):

    leave now  ⟺  your wait  ≤  your travel time + a small buffer

Both halves are approximations, so this module is explicit about being one: it
uses an average urban speed, not live traffic, and it says so in the note text
rather than pretending to be a maps app.

Design rules (same contract as ``ewt.py``):
  * PURE FUNCTIONS ONLY — no network, no DB, no geolocation SDK. The browser
    supplies coordinates; the server does arithmetic.
  * Never invent a distance. With no coordinates there is no travel estimate,
    and the caller falls back to the old wait-only message.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

# ── Tunables (one place, so tests and production agree) ─────────────────────

#: Average door-to-door urban speed in an Indian city, km/h. Deliberately
#: conservative: a two-wheeler in traffic, not a highway average.
URBAN_SPEED_KMPH: float = 18.0

#: Minutes added for parking / finding the entrance / reception queue.
DEFAULT_BUFFER_MINUTES: int = 8

#: Beyond this the estimate is guesswork, so we stop short of a number.
MAX_USEFUL_DISTANCE_KM: float = 120.0

#: Earth radius, km.
_EARTH_RADIUS_KM: float = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two coordinates."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(max(0.0, min(1.0, a))))


def _coords(value: Any) -> float | None:
    """Parse a coordinate, or None when it is missing/unusable."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def distance_km(
    patient_lat: Any, patient_lon: Any, clinic_lat: Any, clinic_lon: Any
) -> float | None:
    """Distance patient → clinic in km, or None when either side is unknown."""
    plat, plon = _coords(patient_lat), _coords(patient_lon)
    clat, clon = _coords(clinic_lat), _coords(clinic_lon)
    if None in (plat, plon, clat, clon):
        return None
    if plat == 0.0 and plon == 0.0:  # the classic "no GPS fix" placeholder
        return None
    if clat == 0.0 and clon == 0.0:
        return None
    return haversine_km(plat, plon, clat, clon)


def travel_minutes(
    distance: Any,
    speed_kmph: float = URBAN_SPEED_KMPH,
    buffer_minutes: int = DEFAULT_BUFFER_MINUTES,
) -> int | None:
    """Estimated minutes to reach the clinic, buffer included.

    Returns None when there is no usable distance, so callers can print the
    honest old message instead of a made-up "12 min".
    """
    km = _coords(distance)
    if km is None or km < 0:
        return None
    if km > MAX_USEFUL_DISTANCE_KM:
        return None
    speed = float(speed_kmph) if speed_kmph and speed_kmph > 0 else URBAN_SPEED_KMPH
    driving = (km / speed) * 60.0
    # Short hops are dominated by getting out of the door, not by the road.
    try:
        extra = max(0, int(buffer_minutes or 0))
    except (TypeError, ValueError):
        extra = DEFAULT_BUFFER_MINUTES
    return int(round(driving)) + extra


def leave_decision(
    wait_minutes: Any,
    travel: Any,
    buffer: int = 0,
) -> dict[str, Any]:
    """Decide whether NOW is the moment to start moving.

    Args:
        wait_minutes: the patient's estimated wait (from the EWT engine).
        travel: travel minutes from :func:`travel_minutes`, or None if unknown.
        buffer: extra slack the caller wants on top of the travel time.

    Returns:
        A dict with ``should_leave``, ``urgency``, ``slack_minutes`` and
        ``has_travel`` — never raises, always safe to render.
    """
    try:
        wait = max(0, int(wait_minutes or 0))
    except (TypeError, ValueError):
        wait = 0

    travel_int = None
    if travel is not None:
        try:
            travel_int = max(0, int(travel))
        except (TypeError, ValueError):
            travel_int = None

    if travel_int is None:
        # No coordinates → keep the old wait-only behaviour (>= 15 min slack).
        return {
            "should_leave": wait <= 15,
            "urgency": "now" if wait <= 8 else ("soon" if wait <= 15 else "wait"),
            "slack_minutes": None,
            "has_travel": False,
        }

    try:
        pad = max(0, int(buffer or 0))
    except (TypeError, ValueError):
        pad = 0

    slack = wait - (travel_int + pad)
    if slack <= 0:
        urgency = "late"  # already short on time — go immediately
    elif slack <= 5:
        urgency = "now"
    elif slack <= 15:
        urgency = "soon"
    else:
        urgency = "wait"

    return {
        "should_leave": slack <= 5,
        "urgency": urgency,
        "slack_minutes": slack,
        "has_travel": True,
        "travel_minutes": travel_int,
    }


def departure_message(
    token: Any,
    wait_minutes: Any,
    travel: Any = None,
    buffer: int = 0,
) -> str:
    """The WhatsApp body for a departure alert — Hinglish, honest, one screen.

    With travel time it advises on timing; without it, it falls back to the
    plain "ab niklo" wording so nothing regresses for a patient who never
    shared a location.
    """
    decision = leave_decision(wait_minutes, travel, buffer)
    try:
        wait = max(0, int(wait_minutes or 0))
    except (TypeError, ValueError):
        wait = 0

    header = f"🏃 GIL CLINIC — Token #{token}\n\n"
    if not decision["has_travel"]:
        return (
            f"{header}Aapse ~{wait} min ka wait hai.\n"
            "Clinic pahunch kar reception par token dikhaiye."
        )

    travel_min = int(decision.get("travel_minutes") or 0)
    slack = decision.get("slack_minutes")
    urgency = decision["urgency"]

    if urgency == "late":
        advice = (
            f"Aapka rasta ~{travel_min} min ka hai aur wait sirf ~{wait} min — "
            "aap thoda late ho sakte hain. Nikalne se pehle reception ko call kar lein."
        )
    elif urgency == "now":
        advice = f"Abhi nikliye — rasta ~{travel_min} min, wait ~{wait} min. Timing perfect hai."
    elif urgency == "soon":
        advice = f"{max(0, int(slack or 0))} min me nikliye — rasta ~{travel_min} min ka hai."
    else:
        advice = (
            f"Abhi jaldi nahi — wait ~{wait} min hai, rasta ~{travel_min} min. "
            f"Lagbhag {max(0, int(slack or 0))} min baad nikliye."
        )

    return f"{header}{advice}\n\nLocation: clinic pahunch kar reception par token dikhaiye."


def now_iso() -> str:
    """UTC timestamp for stamping an alert (kept here so callers stay pure)."""
    return datetime.now(timezone.utc).isoformat()
