"""Opening hours — is this clinic actually open right now?

Why this file exists
--------------------
"Find a Doctor" called every licensed clinic ``OPEN`` — at 11 PM, on a Sunday,
on Diwali. So a patient picked a clinic, travelled 12 km, found a shutter down,
and blamed the clinic rather than the directory. Availability that is not real
is worse than no availability at all, because it costs the patient a journey.

What this module answers, and nothing else:

    "Kya ye clinic abhi khuli hai?"        → OPEN / CLOSING_SOON / CLOSED / HOLIDAY
    "Agar band hai to kab khulegi?"        → next_opening() → "Kal 09:00"

Design rules (deliberate, do not break):
  * PURE FUNCTIONS ONLY — no DB, no ORM, no FastAPI, no network. Same rule as
    ``src/domain/queue/ewt.py``, so the whole thing is unit-testable and can be
    called from the marketplace, the API, or a template helper.
  * Missing hours must never HIDE a clinic (a clinic with no hours configured
    stays available). Availability is an enrichment, not a gate on the
    directory — otherwise a data-entry gap silently deletes a paying partner.
  * Times are clinic-local (IST). The rest of the app stores UTC, so this is the
    one place that converts, using an injectable clock for tests.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

# ── Vocabulary (kept as plain strings so JSON, DB and templates agree) ───────

OPEN = "OPEN"
CLOSING_SOON = "CLOSING_SOON"
CLOSED = "CLOSED"
HOLIDAY = "HOLIDAY"
DIRECTORY = "DIRECTORY"

#: Human labels — Hinglish, because this is what patients and reception read.
AVAILABILITY_LABEL: dict[str, str] = {
    OPEN: "🟢 Abhi khula hai",
    CLOSING_SOON: "🟡 Band hone wali hai",
    CLOSED: "🔴 Abhi band hai",
    HOLIDAY: "🔴 Aaj chhutti hai",
    DIRECTORY: "📞 Call karke confirm karein",
}

#: Short badge text for a compact card / chip.
AVAILABILITY_BADGE: dict[str, str] = {
    OPEN: "🟢 Khula",
    CLOSING_SOON: "🟡 Jaldi band",
    CLOSED: "🔴 Band",
    HOLIDAY: "🔴 Chhutti",
    DIRECTORY: "📞 Directory",
}

#: Defaults used when a clinic has not configured its hours yet.
DEFAULT_OPEN_TIME = "09:00"
DEFAULT_CLOSE_TIME = "18:00"

#: Inside this many minutes of closing time we warn instead of promising.
CLOSING_SOON_MINUTES: int = 45

#: The clinic's local timezone. India has a single zone and no DST.
CLINIC_TZ = timezone(timedelta(hours=5, minutes=30), name="IST")

#: Weekday names → Python weekday() numbers (Monday = 0 … Sunday = 6).
_WEEKDAY_ALIASES: dict[str, int] = {
    "monday": 0, "mon": 0, "somvar": 0, "somwar": 0,
    "tuesday": 1, "tue": 1, "tues": 1, "mangalvar": 1, "mangalwar": 1,
    "wednesday": 2, "wed": 2, "budhvar": 2, "budhwar": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3, "guruvar": 3, "guruwar": 3,
    "friday": 4, "fri": 4, "shukravar": 4, "shukrawar": 4,
    "saturday": 5, "sat": 5, "shanivar": 5, "shaniwar": 5,
    "sunday": 6, "sun": 6, "ravivar": 6, "raviwar": 6,
}

#: Display names for next_opening().
_WEEKDAY_SHORT: dict[int, str] = {
    0: "Som", 1: "Mangal", 2: "Budh", 3: "Guru", 4: "Shukra", 5: "Shani", 6: "Ravi",
}


# ── Parsing (never raises — bad input degrades to "unknown") ─────────────────


def local_now(now: datetime | None = None) -> datetime:
    """Current clinic-local time. An aware ``now`` is converted, not trusted."""
    if now is None:
        return datetime.now(CLINIC_TZ)
    if now.tzinfo is None:
        # Naive input is assumed to already be clinic-local (tests + templates).
        return now.replace(tzinfo=CLINIC_TZ)
    return now.astimezone(CLINIC_TZ)


def parse_time(value: Any) -> time | None:
    """``"09:00"`` / ``"9:00"`` / ``"9"`` / ``"09:00:00"`` → ``time``, else None.

    Accepts what a human types into an ``<input type="time">`` or a free-text
    field. Unparseable input returns None so the caller can fall back to a
    default instead of guessing.
    """
    if isinstance(value, time):
        return value
    if isinstance(value, datetime):
        return value.time()
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Tolerate "9.00", "9:00 AM", "0900", "09:00:00"
    text = text.upper().replace(".", ":").replace(" ", "")
    ampm = ""
    for suffix in ("AM", "PM"):
        if text.endswith(suffix):
            ampm = suffix
            text = text[: -len(suffix)]
            break
    parts = text.split(":")
    if len(parts) == 1 and len(parts[0]) == 4 and parts[0].isdigit():
        parts = [parts[0][:2], parts[0][2:]]  # "0900" → 09:00
    if not parts or not parts[0].strip():
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 and parts[1].strip() else 0
    except (TypeError, ValueError):
        return None
    if ampm == "PM" and hour < 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return time(hour=hour, minute=minute)


def parse_closed_days(value: Any) -> set[int]:
    """``"Sunday"`` / ``"sun,sat"`` / ``"6,5"`` / ``"6 5"`` → ``{5, 6}``.

    Understands English names, common Hindi names, and raw weekday numbers
    (Monday = 0), because all three end up in the same admin field.
    """
    days: set[int] = set()
    if value is None:
        return days
    if isinstance(value, int) and not isinstance(value, bool):
        return {value % 7} if 0 <= value % 7 <= 6 else days
    if isinstance(value, (list, tuple, set)):
        items = [str(v) for v in value]
    else:
        items = str(value).replace(";", ",").replace("|", ",").replace(" ", ",").split(",")
    for raw in items:
        token = str(raw).strip().lower()
        if not token:
            continue
        if token in _WEEKDAY_ALIASES:
            days.add(_WEEKDAY_ALIASES[token])
            continue
        try:
            number = int(token)
        except (TypeError, ValueError):
            continue
        if 0 <= number <= 6:
            days.add(number)
    return days


def parse_date(value: Any) -> date | None:
    """``"2026-03-14"`` (or a datetime) → ``date``, else None."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


# ── Time windows ────────────────────────────────────────────────────────────


def _window(
    open_time: Any, close_time: Any
) -> tuple[time, time] | None:
    """Resolved ``(open, close)``, or None when hours are not usable.

    A clinic with no configured hours returns None — the caller then treats it
    as "unknown" rather than "closed".
    """
    start = parse_time(open_time)
    end = parse_time(close_time)
    if start is None or end is None:
        return None
    if start == end:
        # Same clock time reads as a typo, not a 24-hour clinic.
        return None
    return start, end


def _in_window(moment: time, start: time, end: time) -> bool:
    """Is ``moment`` inside the window, including overnight (22:00 → 02:00)?"""
    if start <= end:
        return start <= moment < end
    return moment >= start or moment < end  # crosses midnight


def minutes_until_close(
    open_time: Any, close_time: Any, now: datetime | None = None
) -> int | None:
    """Minutes left before closing, or None when unknown / already closed."""
    window = _window(open_time, close_time)
    if window is None:
        return None
    start, end = window
    moment = local_now(now)
    current = moment.time()
    if not _in_window(current, start, end):
        return None
    close_dt = moment.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if end <= start:  # overnight → closing happens tomorrow
        close_dt += timedelta(days=1)
    return max(0, int((close_dt - moment).total_seconds() // 60))


def is_holiday(holiday_until: Any, now: datetime | None = None) -> bool:
    """Is the clinic on declared holiday right now?

    ``holiday_until`` is the LAST closed day (inclusive), so a single closure
    and a whole Diwali week are the same field with no ranges to parse.
    """
    until = parse_date(holiday_until)
    if until is None:
        return False
    return local_now(now).date() <= until


def is_closed_day(closed_days: Any, now: datetime | None = None) -> bool:
    """Is today one of the clinic's weekly off days?"""
    return local_now(now).weekday() in parse_closed_days(closed_days)


def has_hours(open_time: Any, close_time: Any) -> bool:
    """True when this clinic has usable opening hours configured."""
    return _window(open_time, close_time) is not None


# ── The answer ──────────────────────────────────────────────────────────────


def availability_state(
    open_time: Any = None,
    close_time: Any = None,
    closed_days: Any = None,
    holiday_until: Any = None,
    now: datetime | None = None,
    is_partner: bool = True,
) -> str:
    """The single source of truth for "abhi khula hai?".

    Order matters and is deliberate:

      1. Not a partner → :data:`DIRECTORY`. A clinic without the live product
         cannot promise a queue, so it never claims to be "open" here.
      2. Holiday → :data:`HOLIDAY` (beats weekly-off: the message differs).
      3. Weekly off day → :data:`CLOSED`.
      4. No hours configured → :data:`OPEN`. **Never hide a clinic because of a
         missing data-entry field.**
      5. Inside the window, closing within :data:`CLOSING_SOON_MINUTES`
         → :data:`CLOSING_SOON`; otherwise :data:`OPEN`.
      6. Outside the window → :data:`CLOSED`.
    """
    if not is_partner:
        return DIRECTORY
    if is_holiday(holiday_until, now):
        return HOLIDAY
    if is_closed_day(closed_days, now):
        return CLOSED

    window = _window(open_time, close_time)
    if window is None:
        return OPEN  # unknown hours must not hide the clinic

    start, end = window
    moment = local_now(now)
    if not _in_window(moment.time(), start, end):
        return CLOSED
    left = minutes_until_close(open_time, close_time, now)
    if left is not None and left <= CLOSING_SOON_MINUTES:
        return CLOSING_SOON
    return OPEN


def is_open_now(
    open_time: Any = None,
    close_time: Any = None,
    closed_days: Any = None,
    holiday_until: Any = None,
    now: datetime | None = None,
    is_partner: bool = True,
) -> bool:
    """Convenience predicate — is the clinic taking patients right now?"""
    return availability_state(
        open_time=open_time,
        close_time=close_time,
        closed_days=closed_days,
        holiday_until=holiday_until,
        now=now,
        is_partner=is_partner,
    ) in (OPEN, CLOSING_SOON)


def within_hours(
    open_time: Any = None,
    close_time: Any = None,
    closed_days: Any = None,
    holiday_until: Any = None,
    now: datetime | None = None,
) -> bool:
    """Schedule-only check: do this clinic's stated hours cover right now?

    Unlike :func:`is_open_now` this ignores partner/tier status, so the
    marketplace's "🟢 Abhi khula hai" filter can also cover directory-only
    clinics — a Tier-2 clinic genuinely open at 4 PM should not vanish from a
    search for open clinics just because it has no live queue.

    A clinic with no hours configured counts as open: an empty field is a
    data-entry gap, not evidence that the shutter is down.
    """
    if is_holiday(holiday_until, now):
        return False
    if is_closed_day(closed_days, now):
        return False
    window = _window(open_time, close_time)
    if window is None:
        return True
    start, end = window
    return _in_window(local_now(now).time(), start, end)


def availability_label(state: str) -> str:
    """Hinglish label for a state (falls back to the directory wording)."""
    return AVAILABILITY_LABEL.get((state or "").upper(), AVAILABILITY_LABEL[DIRECTORY])


def availability_badge(state: str) -> str:
    """Compact badge text for a card / chip."""
    return AVAILABILITY_BADGE.get((state or "").upper(), AVAILABILITY_BADGE[DIRECTORY])


def hours_label(open_time: Any, close_time: Any) -> str:
    """``"09:00 – 18:00"`` for display, or ``""`` when hours are unknown."""
    window = _window(open_time, close_time)
    if window is None:
        return ""
    start, end = window
    return f"{start.strftime('%H:%M')} – {end.strftime('%H:%M')}"


def next_opening(
    open_time: Any = None,
    close_time: Any = None,
    closed_days: Any = None,
    holiday_until: Any = None,
    now: datetime | None = None,
) -> str:
    """When will this clinic next open? ``"Aaj 09:00"`` / ``"Kal 09:00"`` / ``""``.

    Looks ahead 14 days, skipping closed days and declared holidays.

    Returns an empty string in the two cases where there is nothing useful to
    say, so the UI simply omits the line instead of printing noise:

      * the clinic is **open right now** — announcing "Kal 09:00" to a patient
        standing at an open counter is worse than saying nothing;
      * no hours are configured — we will not invent a schedule.
    """
    window = _window(open_time, close_time)
    if window is None:
        return ""
    start, end = window
    moment = local_now(now)
    off_days = parse_closed_days(closed_days)
    until = parse_date(holiday_until)

    if moment.weekday() not in off_days and (until is None or moment.date() > until):
        if _in_window(moment.time(), start, end):
            return ""  # already open — nothing to announce

    for offset in range(0, 15):
        day = moment.date() + timedelta(days=offset)
        if day.weekday() in off_days:
            continue
        if until is not None and day <= until:
            continue
        opens_at = datetime.combine(day, start, tzinfo=CLINIC_TZ)
        if opens_at <= moment:
            continue
        label = start.strftime("%H:%M")
        if offset == 0:
            return f"Aaj {label}"
        if offset == 1:
            return f"Kal {label}"
        return f"{_WEEKDAY_SHORT.get(day.weekday(), '')} {label}".strip()
    return ""


def closing_note(
    open_time: Any, close_time: Any, now: datetime | None = None
) -> str:
    """One honest Hinglish line about today's hours, for a card or a call.

    Examples: ``"Aaj 18:00 tak khula hai"`` · ``"Kal 09:00 par khulega"`` ·
    ``""`` when hours are unknown.
    """
    window = _window(open_time, close_time)
    if window is None:
        return ""
    _start, end = window
    left = minutes_until_close(open_time, close_time, now=now)
    if left is None:
        nxt = next_opening(open_time, close_time, now=now)
        return f"{nxt} par khulega" if nxt else ""
    if left <= CLOSING_SOON_MINUTES:
        return f"{left} min me band ho jayega ({end.strftime('%H:%M')})"
    return f"Aaj {end.strftime('%H:%M')} tak khula hai"


def to_public_dict(
    open_time: Any = None,
    close_time: Any = None,
    closed_days: Any = None,
    holiday_until: Any = None,
    now: datetime | None = None,
    is_partner: bool = True,
) -> dict[str, Any]:
    """JSON-safe availability bundle for the marketplace API / templates."""
    state = availability_state(
        open_time=open_time,
        close_time=close_time,
        closed_days=closed_days,
        holiday_until=holiday_until,
        now=now,
        is_partner=is_partner,
    )
    starts = parse_time(open_time)
    ends = parse_time(close_time)
    holiday = parse_date(holiday_until)
    return {
        "state": state,
        "label": availability_label(state),
        "badge": availability_badge(state),
        "badge_type": (
            "success" if state == OPEN
            else "warning" if state == CLOSING_SOON
            else "muted"
        ),
        "is_open": state in (OPEN, CLOSING_SOON),
        "open_time": starts.strftime("%H:%M") if starts else "",
        "close_time": ends.strftime("%H:%M") if ends else "",
        "hours": hours_label(open_time, close_time),
        "minutes_until_close": minutes_until_close(open_time, close_time, now),
        "closed_days": sorted(parse_closed_days(closed_days)),
        "holiday_until": holiday.isoformat() if holiday else "",
        "next_opening": next_opening(open_time, close_time, closed_days, holiday_until, now),
        "closing_note": closing_note(open_time, close_time, now),
    }
