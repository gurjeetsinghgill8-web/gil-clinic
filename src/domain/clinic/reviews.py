"""Verified reviews + Bayesian rating (Part F · F-07).

Why this module exists
---------------------
An unverified star rating is worse than no rating. One angry competitor, one
happy cousin, and the number stops meaning anything — and a patient who chose a
clinic on that number never learns why they were misled.

Two rules make the rating mean something:

  **Verified.** A review can only be written from a tracking link for a visit
  that actually completed. The token is the proof of the visit, so the review
  cannot exist without one. No signup, no "rate us" email, no anonymous drive-by.

  **Bayesian.** The displayed score is shrunk toward a prior:

      score = (C × m + Σ ratings) / (C + n)

  where ``m`` is the prior mean and ``C`` the prior weight. Without this, a
  clinic with a single 5★ review outranks one with 200 reviews averaging 4.8 —
  the classic small-sample lie. With it, a new clinic's score moves gradually as
  real evidence accumulates, which is what "verified" should feel like.

Design rules: PURE FUNCTIONS ONLY — no DB, no ORM, no FastAPI.
"""

from __future__ import annotations

from typing import Any, Iterable

#: Prior mean: what we assume about a clinic we know nothing about. Slightly
#: above the midpoint because a registered clinic is at least a real clinic —
#: but nowhere near a top score, because we have no evidence yet.
PRIOR_MEAN: float = 3.8

#: Prior weight, in "imaginary reviews". With C=5, a clinic needs roughly 5 real
#: reviews before its own average outweighs the prior, and ~20 before the score
#: is mostly its own — the honest pace at which a rating should earn trust.
PRIOR_WEIGHT: float = 5.0

#: Ratings are 1–5 stars.
MIN_RATING = 1
MAX_RATING = 5

#: Visit states that prove the patient actually saw the doctor.
REVIEWABLE_STATUSES: tuple[str, ...] = ("COMPLETED", "REPORT_READY", "DELIVERED")

#: How long after the visit a review may still be written (days).
REVIEW_WINDOW_DAYS = 60


def is_reviewable_status(status: Any) -> bool:
    """Did this visit actually happen? Only a completed visit can be reviewed."""
    return str(status or "").strip().upper() in REVIEWABLE_STATUSES


def eligibility(entry: Any, now: Any = None, window_days: int = REVIEW_WINDOW_DAYS) -> tuple[bool, str]:
    """Can this visit be reviewed? Returns ``(allowed, reason_in_hinglish)``.

    Kept as data-in/data-out so the same rule governs the API and the UI, and
    so the reason given to the patient is the same one the code enforced.
    """
    if entry is None:
        return False, "Visit nahi mila — review sirf asli visit ke baad."

    status = entry.get("status") if isinstance(entry, dict) else getattr(entry, "status", None)
    if not is_reviewable_status(status):
        return False, "Review visit poori hone ke baad hi likha ja sakta hai."

    if now is not None:
        completed = (
            entry.get("completed_at")
            if isinstance(entry, dict)
            else getattr(entry, "completed_at", None)
        )
        if completed is not None:
            from datetime import datetime, timedelta, timezone

            moment = now if getattr(now, "tzinfo", None) else now.replace(tzinfo=timezone.utc)
            stamp = completed if getattr(completed, "tzinfo", None) else completed.replace(tzinfo=timezone.utc)
            if moment - stamp > timedelta(days=max(1, int(window_days))):
                return False, "Is visit ke review ka time nikal gaya."

    return True, ""


def clamp_rating(value: Any) -> int | None:
    """Coerce a star value to 1–5, or None when it is not a usable rating."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < MIN_RATING or number > MAX_RATING:
        return None
    return number


def bayesian_rating(
    ratings: Iterable[Any] | None,
    prior_mean: float = PRIOR_MEAN,
    prior_weight: float = PRIOR_WEIGHT,
) -> float | None:
    """Shrunk average of the given ratings, or None when there are none.

    ``None`` (rather than the prior) when there is no data, so the caller can
    omit the star display entirely instead of showing a number nobody earned.
    """
    values = [r for r in (clamp_rating(v) for v in (ratings or [])) if r is not None]
    if not values:
        return None
    try:
        mean = float(prior_mean)
        weight = max(0.0, float(prior_weight))
    except (TypeError, ValueError):
        mean, weight = PRIOR_MEAN, PRIOR_WEIGHT
    total = sum(values)
    count = len(values)
    return round((weight * mean + total) / (weight + count), 2)


def rating_breakdown(ratings: Iterable[Any] | None) -> dict[str, Any]:
    """Full rating picture for a clinic card or an admin table."""
    values = [r for r in (clamp_rating(v) for v in (ratings or [])) if r is not None]
    count = len(values)
    if not count:
        return {
            "rating": None,
            "count": 0,
            "raw_average": None,
            "distribution": {},
            "confidence": "no_data",
            "note": "Abhi koi verified review nahi.",
        }
    raw = round(sum(values) / count, 2)
    distribution = {str(star): values.count(star) for star in range(MIN_RATING, MAX_RATING + 1)}
    score = bayesian_rating(values)

    # Confidence is about SAMPLE SIZE, not about the score itself — a 5.0 from
    # two reviews must never look as solid as a 4.6 from two hundred.
    if count >= 50:
        confidence = "high"
    elif count >= 15:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "rating": score,
        "count": count,
        "raw_average": raw,
        "distribution": distribution,
        "confidence": confidence,
        "note": rating_note(count, score, raw, confidence),
    }


def rating_note(count: int, score: float | None, raw: float | None, confidence: str) -> str:
    """One Hinglish line that keeps the number honest about itself."""
    if confidence == "low":
        return (
            f"Sirf {count} verified review — score dheere-dheere settle hoga "
            "(ek-do review se number nahi badalta)."
        )
    if confidence == "medium":
        return f"{count} verified reviews · average {raw} · score {score}."
    return f"{count} verified reviews · average {raw} · bharosemand score {score}."


def sort_weight(rating: Any, count: Any) -> float:
    """Ranking contribution — zero when unrated, so absence never penalises.

    A clinic with no reviews is *unknown*, not bad, and the marketplace must not
    bury a genuinely good clinic simply because nobody has reviewed it yet.
    """
    score = None
    try:
        if rating is not None:
            score = float(rating)
    except (TypeError, ValueError):
        score = None
    if score is None:
        return 0.0
    try:
        n = max(0, int(count or 0))
    except (TypeError, ValueError):
        n = 0
    trust = min(1.0, n / 20.0)
    return (score - 3.5) * 40.0 * (0.35 + 0.65 * trust)
