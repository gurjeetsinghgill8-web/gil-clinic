"""Discovery ranking + computed tags for "Find a Doctor" (Part F · F-04 / F-05).

Why this file exists
--------------------
The directory used to rank by ``is_license_active DESC, doctor_name ASC`` —
which means a clinic with an empty chamber at 6 minutes' walk could sit below
one that is two hours behind and 40 km away, purely because of its name. The
patient then picks the wrong clinic, waits two hours, and stops trusting the
number.

Two things replace that:

  **Tags** (F-05) — structured, computed from data the app already has. No
  hand-placed emoji, no marketing copy: a badge exists only because a fact
  behind it exists, and it disappears the moment the fact stops being true.

  **A score** (F-04) — proximity, live queue depth, how much we trust that
  queue number, real availability, and rating, combined into one number.
  The two-tier rule (partner above directory) is enforced by the SORT KEY, not
  by the score, so tuning the weights can never silently break that promise.

Design rules:
  * PURE FUNCTIONS ONLY — no DB, no ORM, no FastAPI. Same contract as
    ``ewt.py`` and ``opening_hours.py``.
  * **Cold-start honesty.** A clinic with no consultation history gets its
    wait-time advantage *damped*, not rewarded. Otherwise a brand-new clinic
    would top every search simply because we know nothing about it — and the
    first patient through the door would discover the number was fiction.
  * Distance is a sigmoid, not a step: 1 km vs 2 km matters, 40 km vs 41 km
    does not.
"""

from __future__ import annotations

import math
from typing import Any

from src.domain.queue import ewt

# ── Tags (F-05) ─────────────────────────────────────────────────────────────

TAG_LIVE_TELEMETRY = "LIVE_TELEMETRY"
TAG_INSTANT_TOKEN = "INSTANT_TOKEN"
TAG_ZERO_WAIT_VERIFIED = "ZERO_WAIT_VERIFIED"
TAG_OPEN_NOW = "OPEN_NOW"
TAG_CLOSING_SOON = "CLOSING_SOON"
TAG_CLOSED_TODAY = "CLOSED_TODAY"
TAG_HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
TAG_NEARBY = "NEARBY"
TAG_DIRECT_CALL_ONLY = "DIRECT_CALL_ONLY"

#: Hinglish labels — this is what the patient reads on the card.
TAG_LABEL: dict[str, str] = {
    TAG_LIVE_TELEMETRY: "🟢 Live queue",
    TAG_INSTANT_TOKEN: "⚡ Abhi turant turn",
    TAG_ZERO_WAIT_VERIFIED: "✅ Zero wait (verified)",
    TAG_OPEN_NOW: "🟢 Abhi khula",
    TAG_CLOSING_SOON: "🟡 Jaldi band",
    TAG_CLOSED_TODAY: "🔴 Aaj band",
    TAG_HIGH_CONFIDENCE: "🎯 Bharosemand ETA",
    TAG_NEARBY: "📍 Paas me",
    TAG_DIRECT_CALL_ONLY: "📞 Call karke confirm",
}

#: Short one-line explanation per tag, for a tooltip or the results legend.
TAG_HINT: dict[str, str] = {
    TAG_LIVE_TELEMETRY: "Is clinic ka live queue is waqt chal raha hai.",
    TAG_INSTANT_TOKEN: "Koi patient aage nahi — token lete hi turn.",
    TAG_ZERO_WAIT_VERIFIED: "Zero wait, aur clinic ke asli data se confirm.",
    TAG_OPEN_NOW: "Clinic ke bataye hours ke hisaab se abhi khuli hai.",
    TAG_CLOSING_SOON: "Band hone wali hai — jaane se pehle call kar lein.",
    TAG_CLOSED_TODAY: "Abhi band hai — token pehle book kar sakte hain.",
    TAG_HIGH_CONFIDENCE: "Kaafi consultation history hai, number bharosemand.",
    TAG_NEARBY: "Aapki location se paas me.",
    TAG_DIRECT_CALL_ONLY: "Live queue nahi hai — clinic ko direct call karein.",
}

# ── Score weights (one place, so tests and production agree) ────────────────

#: Distance at which "nearby" stops being remarkable, km.
NEARBY_KM = 5.0

#: How much a fully-trusted short wait is worth.
MAX_WAIT_BONUS = 250.0
#: Minutes at which the wait bonus reaches zero.
WAIT_BONUS_ZERO_AT = 60.0
#: Maximum distance bonus (at zero km).
MAX_DISTANCE_BONUS = 200.0
#: Rating contribution per star above the baseline, scaled by review trust in
#: ``reviews.sort_weight``. Kept here only as documentation of the magnitude.
RATING_WEIGHT = 40.0
#: Neutral rating — below this the score goes negative rather than just smaller.
RATING_BASELINE = 3.5
#: Availability contributions.
OPEN_BONUS = 120.0
CLOSING_SOON_BONUS = 60.0
CLOSED_PENALTY = -150.0


def compute_tags(doctor: dict[str, Any], nearby_km: float = NEARBY_KM) -> list[str]:
    """Structured badges for one directory entry, derived only from real data.

    Order is deliberate (strongest signal first) so a card that shows only the
    first tag shows the most useful one.
    """
    tags: list[str] = []
    live = doctor.get("live") or {}
    partner = bool(doctor.get("partner"))

    if live and live.get("real"):
        tags.append(TAG_LIVE_TELEMETRY)
        if int(live.get("patients_ahead") or 0) == 0 and live.get("state") == "live":
            tags.append(TAG_INSTANT_TOKEN)
            if (live.get("confidence") or "").lower() == "high":
                tags.append(TAG_ZERO_WAIT_VERIFIED)
        if (live.get("confidence") or "").lower() == "high":
            if TAG_HIGH_CONFIDENCE not in tags:
                tags.append(TAG_HIGH_CONFIDENCE)

    state = str(doctor.get("availability") or "").upper()
    if state == "OPEN":
        tags.append(TAG_OPEN_NOW)
    elif state == "CLOSING_SOON":
        tags.append(TAG_CLOSING_SOON)
    elif state in ("CLOSED", "HOLIDAY"):
        tags.append(TAG_CLOSED_TODAY)

    distance = doctor.get("distance_km")
    if distance is not None and float(distance) <= nearby_km:
        tags.append(TAG_NEARBY)

    if not partner:
        tags.append(TAG_DIRECT_CALL_ONLY)

    return tags


def tags_with_labels(tags: list[str]) -> list[dict[str, str]]:
    """``["OPEN_NOW"]`` → ``[{"key":…, "label":…, "hint":…}]`` for the UI."""
    return [
        {
            "key": tag,
            "label": TAG_LABEL.get(tag, tag),
            "hint": TAG_HINT.get(tag, ""),
        }
        for tag in tags
    ]


# ── Score (F-04) ────────────────────────────────────────────────────────────


def _wait_bonus(live: dict[str, Any]) -> float:
    """Reward a genuinely short queue, damped by how much we trust the number.

    The dampener is the important half. A clinic with one completed
    consultation shows "0 min wait" simply because we have no data — awarding
    that the full bonus would put the least-known clinic at the top of every
    search and make the first patient's experience the exact opposite of the
    promise.
    """
    if not live or live.get("state") != "live":
        return 0.0
    try:
        wait = float(live.get("wait_minutes") or 0)
    except (TypeError, ValueError):
        return 0.0

    raw = max(0.0, MAX_WAIT_BONUS * (1.0 - min(wait, WAIT_BONUS_ZERO_AT) / WAIT_BONUS_ZERO_AT))

    try:
        samples = int(live.get("samples") or 0)
    except (TypeError, ValueError):
        samples = 0
    trust = min(1.0, samples / float(ewt.SAMPLES_FOR_HIGH_CONFIDENCE))
    # Floor at 0.25 so a real zero-wait signal is not erased, but never
    # outranks a well-established clinic on its word alone.
    factor = 0.25 + 0.75 * trust
    return raw * factor


def _distance_bonus(distance: Any, nearby_km: float = NEARBY_KM) -> float:
    """Sigmoid: 1 km vs 2 km matters, 40 km vs 41 km does not."""
    if distance is None:
        return 0.0
    try:
        km = float(distance)
    except (TypeError, ValueError):
        return 0.0
    if km < 0:
        return 0.0
    scale = max(1.0, nearby_km / 2.0)
    return MAX_DISTANCE_BONUS / (1.0 + math.exp((km - nearby_km) / scale))


def _availability_bonus(state: str) -> float:
    state = (state or "").upper()
    if state == "OPEN":
        return OPEN_BONUS
    if state == "CLOSING_SOON":
        return CLOSING_SOON_BONUS
    if state in ("CLOSED", "HOLIDAY"):
        return CLOSED_PENALTY
    return 0.0  # DIRECTORY: neutral, the tier already says the rest


def _rating_bonus(rating: Any, rating_count: Any = None) -> float:
    """Rating contribution, damped by how many reviews it is based on.

    A 5.0 from two reviews must not outweigh a 4.6 from two hundred — that is
    the same small-sample lie the Bayesian score exists to prevent, so the
    ranking uses the shared trust weighting from ``reviews.sort_weight`` rather
    than a raw star difference. An unrated clinic scores 0: unknown, not bad.
    """
    from src.domain.clinic import reviews as review_rules

    return review_rules.sort_weight(rating, rating_count)


def rank_score(doctor: dict[str, Any], nearby_km: float = NEARBY_KM) -> float:
    """Quality score for one entry — deliberately WITHOUT the tier bonus.

    The partner-above-directory promise is enforced by the sort key
    (``(tier, -rank_score)``), not by this number, so weights can be tuned
    freely without ever letting a Tier-2 clinic outrank a partner. That
    separation is tested.
    """
    live = doctor.get("live") or {}
    score = 0.0
    score += _wait_bonus(live)
    score += _distance_bonus(doctor.get("distance_km"), nearby_km)
    score += _availability_bonus(str(doctor.get("availability") or ""))
    score += _rating_bonus(doctor.get("rating"), doctor.get("rating_count"))
    return round(score, 2)


def explain(doctor: dict[str, Any], nearby_km: float = NEARBY_KM) -> dict[str, float]:
    """The score's components, so a result can always be justified.

    Never show a ranking the clinic cannot have explained to them.
    """
    live = doctor.get("live") or {}
    return {
        "wait": round(_wait_bonus(live), 2),
        "distance": round(_distance_bonus(doctor.get("distance_km"), nearby_km), 2),
        "availability": round(_availability_bonus(str(doctor.get("availability") or "")), 2),
        "rating": round(
            _rating_bonus(doctor.get("rating"), doctor.get("rating_count")), 2
        ),
        "total": rank_score(doctor, nearby_km),
    }
