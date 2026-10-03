"""EWT — Estimated Wait Time engine ("Uber ETA for OPD").

Why this file exists
--------------------
The marketplace used to show ``patients_ahead × 7`` minutes — a flat guess that
treats a 6-minute follow-up and a 20-minute new case as the same thing. Patients
lost trust in the number, and doctors said the queue "lied".

This module replaces the guess with a self-calibrating estimate:

    EWT = SUM(visit_weight_i × avg_service_minutes)   ← everyone ahead of you
        + delay_penalty(current patient overrunning)
        - elapsed_since_called (if you were already called)

Design rules (deliberate, do not break):
  * PURE FUNCTIONS ONLY — no DB, no network, no FastAPI, no ORM imports.
    That keeps the maths unit-testable and safe to call from anywhere.
  * Self-calibrating — the doctor's REAL average is learned from the
    ``started_at`` → ``completed_at`` pairs the queue engine already records.
  * Honest — if the doctor has not opened the chamber (Part D · E-01) the
    estimate is NOT a countdown; it returns ``arrival_pending`` instead of a
    fabricated number.
  * No fake data — never invent a number to look busy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

# ── Tunables (one place, so tests and production agree) ─────────────────────

#: Fallback consultation length when this doctor has no history yet.
DEFAULT_AVG_MINUTES: float = 7.0

#: Samples needed before we trust the learned average on its own.
MIN_SAMPLES_FOR_TRUST: int = 5

#: Samples needed before we report "high" confidence.
SAMPLES_FOR_HIGH_CONFIDENCE: int = 20

#: Clamp the learned average so one weird day cannot wreck the estimate.
MIN_AVG_MINUTES: float = 2.0
MAX_AVG_MINUTES: float = 45.0

#: A single consultation shorter/longer than this is treated as noise
#: (staff clicked "start" twice, or forgot to complete an entry).
SANE_SERVICE_MINUTES: tuple[float, float] = (1.0, 120.0)

#: Display clamps.
MIN_EWT_MINUTES: int = 2
MAX_EWT_MINUTES: int = 180

#: How much of the current patient's overrun we add to everyone's wait.
MAX_DELAY_PENALTY_MINUTES: float = 15.0

#: Visit-type → multiplier on the doctor's learned average.
#: A "new" case is ~1.8× a routine visit; a report review is a quick 0.6×.
#: "geriatric" comes from the enterprise blueprint's elderly multiplier
#: (70+ consultations consistently run longer than the clinic average).
#: "emergency" (Part D · E-08) jumps the queue but still occupies the chamber,
#: so it must count honestly against everybody else's wait.
VISIT_TYPE_WEIGHT: dict[str, float] = {
    "new": 1.8,
    "procedure": 1.8,
    "emergency": 1.5,
    "geriatric": 1.2,
    "followup": 0.75,
    "report": 0.6,
    "": 1.0,
}

#: DB stores ``complexity_weight`` as an int (1 = routine, 2 = heavy).
COMPLEXITY_WEIGHT_MINUTES: dict[int, float] = {1: 0.85, 2: 1.8, 3: 2.2}

#: Human labels (Hinglish — this is what the clinic staff and patients read).
VISIT_TYPE_LABEL: dict[str, str] = {
    "new": "Naya case",
    "procedure": "Test/Procedure",
    "emergency": "🚨 Emergency",
    "geriatric": "Senior patient",
    "followup": "Follow-up",
    "report": "Report review",
    "": "Consultation",
}

#: How far the recent-velocity signal may bend an estimate.
MIN_VELOCITY: float = 0.7
MAX_VELOCITY: float = 1.4

#: Age at which a consultation is treated as a longer "geriatric" visit.
GERIATRIC_AGE: int = 70


@dataclass(frozen=True)
class WaitEstimate:
    """The answer to "how long will I wait?" — everything the UI needs."""

    minutes: int
    patients_ahead: int
    avg_service_minutes: float
    delay_minutes: float
    confidence: str  # "high" | "medium" | "low"
    state: str  # "live" | "arrival_pending"
    chamber_open: bool
    samples: int = 0
    note: str = ""
    velocity: float = 1.0  # recent pace vs the learned average (1.0 = on time)

    @property
    def is_live(self) -> bool:
        """True when the number is a real countdown (chamber is open)."""
        return self.state == "live"

    def to_public_dict(self) -> dict[str, Any]:
        """Minimal, JSON-safe shape for the marketplace / tracking APIs."""
        return {
            "wait_minutes": self.minutes,
            "patients_ahead": self.patients_ahead,
            "confidence": self.confidence,
            "state": self.state,
            "chamber_open": self.chamber_open,
            "delay_minutes": int(round(self.delay_minutes)),
            "velocity": round(self.velocity, 2),
            "note": self.note,
        }

    def to_line_hi(self) -> str:
        """One short Hinglish line for the patient screen."""
        if not self.chamber_open:
            return "⏳ Doctor abhi chamber me nahi aaye — wait count shuru nahi hua"
        if self.patients_ahead <= 0:
            return "🟢 Aapki baari hai — andar chalein"
        return f"⏳ Aapse {self.patients_ahead} patient aage · ~{self.minutes} min"


# ── Time helpers ────────────────────────────────────────────────────────────


def _as_utc(value: Any) -> datetime | None:
    """Coerce a datetime (naive or aware, from DB or dict) to aware UTC."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            cleaned = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(cleaned)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _field(obj: Any, name: str, default: Any = None) -> Any:
    """Read ``name`` from a dict-like OR an ORM/entity object."""
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def service_minutes(started_at: Any, completed_at: Any) -> float | None:
    """Real consultation length in minutes, or None if unusable.

    Returns None for missing timestamps, negative durations, or values outside
    :data:`SANE_SERVICE_MINUTES` so one bad row cannot poison the average.
    """
    start = _as_utc(started_at)
    end = _as_utc(completed_at)
    if start is None or end is None:
        return None
    minutes = (end - start).total_seconds() / 60.0
    low, high = SANE_SERVICE_MINUTES
    if minutes < low or minutes > high:
        return None
    return minutes


def avg_service_minutes(
    entries: Iterable[Any] | Iterable[float],
    fallback: float = DEFAULT_AVG_MINUTES,
) -> tuple[float, int]:
    """Learn this doctor's average consultation length.

    Accepts either raw floats (minutes) or entry objects/dicts carrying
    ``started_at`` / ``completed_at``. Uses a trimmed mean (drops the single
    longest outlier) and blends toward ``fallback`` while the sample is small.

    Returns:
        ``(average_minutes, sample_count)``
    """
    samples: list[float] = []
    for item in entries or []:
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            value = float(item)
            low, high = SANE_SERVICE_MINUTES
            if low <= value <= high:
                samples.append(value)
            continue
        value = service_minutes(
            _field(item, "started_at"), _field(item, "completed_at")
        )
        if value is not None:
            samples.append(value)

    count = len(samples)
    if count == 0:
        return float(fallback), 0

    values = sorted(samples)
    if count >= 4:
        values = values[:-1]  # drop the single longest consultation
    mean = sum(values) / len(values)

    if count < MIN_SAMPLES_FOR_TRUST:
        # Small sample → lean on the clinic default so early estimates are sane.
        weight = float(count) / float(MIN_SAMPLES_FOR_TRUST)
        mean = (mean * weight) + (float(fallback) * (1.0 - weight))

    return max(MIN_AVG_MINUTES, min(MAX_AVG_MINUTES, mean)), count


def recent_velocity(
    entries: Iterable[Any] | Iterable[float],
    avg_minutes: float,
    window: int = 5,
) -> float:
    """Is the chamber moving faster or slower than its own average, *right now*?

    The blueprint's ``V_t`` signal: the mean of the last ``window`` completed
    consultations divided by the learned average.

        1.0 = on schedule · < 1 = running fast · > 1 = running slow

    Clamped to :data:`MIN_VELOCITY` / :data:`MAX_VELOCITY` so one chaotic
    afternoon cannot distort everybody's estimate.

    The caller should pass entries oldest → newest, because only the tail is
    used. Anything unparsable is skipped rather than guessed.
    """
    durations: list[float] = []
    for item in entries or []:
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            value = float(item)
            low, high = SANE_SERVICE_MINUTES
            if low <= value <= high:
                durations.append(value)
            continue
        value = service_minutes(
            _field(item, "started_at"), _field(item, "completed_at")
        )
        if value is not None:
            durations.append(value)

    if len(durations) < 2 or avg_minutes <= 0:
        return 1.0
    recent = durations[-window:] if len(durations) >= window else durations
    ratio = (sum(recent) / len(recent)) / float(avg_minutes)
    return max(MIN_VELOCITY, min(MAX_VELOCITY, ratio))


# ── Visit classification (Part B · B4.2) ────────────────────────────────────

def classify_visit_type(
    total_visits: int | None = None,
    has_report: bool = False,
    is_procedure: bool = False,
    service_code: str = "OPD",
    age: int | None = None,
    is_emergency: bool = False,
) -> str:
    """Decide new / followup / report / procedure / geriatric / emergency.

    ``age`` comes from the enterprise blueprint's elderly multiplier — senior
    consultations genuinely run longer, so they get their own weight. Order is
    deliberate: an emergency outranks everything, a procedure stays a procedure
    no matter the age.
    """
    if is_emergency:
        return "emergency"
    if is_procedure or (service_code or "").upper() not in ("", "OPD"):
        return "procedure"
    if has_report:
        return "report"
    try:
        visits = int(total_visits or 0)
    except (TypeError, ValueError):
        visits = 0
    if visits <= 1:
        return "new"
    try:
        if age is not None and int(age) >= GERIATRIC_AGE:
            return "geriatric"
    except (TypeError, ValueError):
        pass
    return "followup"


def complexity_weight(visit_type: str) -> int:
    """DB int weight stored alongside ``visit_type`` (1 = routine, 3 = critical)."""
    key = (visit_type or "").strip().lower()
    if key == "emergency":
        return 3
    return 2 if key in ("new", "procedure") else 1


def visit_weight(visit_type: str, complexity_weight_value: int | None = None) -> float:
    """Multiplier applied to the doctor's learned average."""
    key = (visit_type or "").strip().lower()
    if key in VISIT_TYPE_WEIGHT:
        return VISIT_TYPE_WEIGHT[key]
    try:
        return COMPLEXITY_WEIGHT_MINUTES.get(int(complexity_weight_value or 1), 1.0)
    except (TypeError, ValueError):
        return 1.0


def visit_minutes(
    entry: Any,
    avg_minutes: float,
    fallback_minutes: float = DEFAULT_AVG_MINUTES,
) -> float:
    """Estimated minutes this entry will occupy the doctor."""
    weight = visit_weight(
        _field(entry, "visit_type", "") or "",
        _field(entry, "complexity_weight", None),
    )
    base = float(avg_minutes) if avg_minutes else float(fallback_minutes)
    return max(3.0, weight * base)


# ── Live delay (Part B · B3) ────────────────────────────────────────────────


def live_delay_minutes(
    current: Any,
    avg_minutes: float,
    now: datetime | None = None,
) -> float:
    """How far the patient currently inside is overrunning.

    Uses ``started_at`` (falling back to ``called_at``). Returns 0 when nobody
    is inside or when they are still within the expected duration.
    """
    if current is None:
        return 0.0
    reference = _as_utc(_field(current, "started_at")) or _as_utc(
        _field(current, "called_at")
    )
    if reference is None:
        return 0.0
    moment = now or datetime.now(timezone.utc)
    elapsed = (moment - reference).total_seconds() / 60.0
    overrun = elapsed - max(0.0, float(avg_minutes))
    return max(0.0, overrun)


def elapsed_since_called(
    entry: Any, now: datetime | None = None
) -> float:
    """Minutes since this patient was called (0 if never called)."""
    called = _as_utc(_field(entry, "called_at"))
    if called is None:
        return 0.0
    moment = now or datetime.now(timezone.utc)
    return max(0.0, (moment - called).total_seconds() / 60.0)


def elapsed_since_started(entry: Any, now: datetime | None = None) -> float:
    """Minutes the current patient has been inside the chamber (0 if unknown)."""
    started = _as_utc(_field(entry, "started_at"))
    if started is None:
        return 0.0
    moment = now or datetime.now(timezone.utc)
    return max(0.0, (moment - started).total_seconds() / 60.0)


# ── E-07 · No-show detection ────────────────────────────────────────────────

#: A patient who was CALLED but has not entered the chamber within this many
#: minutes is treated as a no-show. Tuned to the walk from the waiting area to
#: the door: long enough that a slow walk or a washroom stop is not punished,
#: short enough that an empty chamber is not left idle for a whole slot.
NO_SHOW_AFTER_MINUTES: int = 8


def minutes_since_called(entry: Any, now: datetime | None = None) -> float | None:
    """Minutes since this entry was called, or None when it never was.

    Unlike :func:`elapsed_since_called` this distinguishes "never called"
    (None) from "called a moment ago" (0.0) — the no-show rule needs that
    difference, because an uncalled patient must never be swept away.
    """
    called = _as_utc(_field(entry, "called_at"))
    if called is None:
        return None
    moment = now or datetime.now(timezone.utc)
    return max(0.0, (moment - called).total_seconds() / 60.0)


def is_no_show(
    entry: Any,
    now: datetime | None = None,
    threshold: int = NO_SHOW_AFTER_MINUTES,
) -> bool:
    """Has this patient failed to show up after being called?

    Only a **CALLED** entry can become a no-show. WAITING is untouched (they
    were never summoned, so leaving them waiting is not their fault), HOLD is
    untouched (they explicitly stepped out — E-02 already protects them), and
    anything IN_PROGRESS or completed is obviously present.
    """
    if entry is None:
        return False
    status = str(_field(entry, "status", "") or "").upper()
    if status != "CALLED":
        return False
    waited = minutes_since_called(entry, now=now)
    if waited is None:
        return False  # called_at missing → do not punish an unknown
    try:
        limit = max(1, int(threshold))
    except (TypeError, ValueError):
        limit = NO_SHOW_AFTER_MINUTES
    return waited >= limit


def sweep_no_shows(
    entries: Iterable[Any] | None,
    now: datetime | None = None,
    threshold: int = NO_SHOW_AFTER_MINUTES,
) -> tuple[list[Any], list[Any]]:
    """Split today's live entries into ``(no_shows, still_present)``.

    Pure: it decides, it does not write. The route applies the verdict, which
    keeps the rule testable with hand-built objects and no database.

    Returns the two lists in their original order, so the caller can keep
    using the second list for the EWT feed exactly as it arrived.
    """
    absent: list[Any] = []
    present: list[Any] = []
    for entry in entries or []:
        (absent if is_no_show(entry, now=now, threshold=threshold) else present).append(entry)
    return absent, present


def no_show_recovery_note(token: Any, waited_minutes: float | None) -> str:
    """Hinglish explanation for the reception desk (BLOCK 2 · E-07)."""
    if waited_minutes is None:
        return f"Token #{token} ko 8 min tak awaz di gayi — abhi line me wapas laayein."
    minutes = int(round(waited_minutes))
    return (
        f"Token #{token} ne {minutes} min tak jawab nahi diya — abhi line me wapas laayein?"
    )


# ── F-03 · EWT accuracy: promised vs delivered ──────────────────────────────

#: A promise is considered accurate within this many minutes either way.
ACCURACY_TOLERANCE_MINUTES: int = 5


def delivered_wait_minutes(entry: Any) -> float | None:
    """How long the patient ACTUALLY waited, in minutes, or None if unknown.

    Measured booking → called (falling back to started), which is the wait the
    patient experienced standing in the room — not the consultation length.
    Returns None rather than guessing when either timestamp is missing, because
    a fabricated sample would corrupt the very metric that exists to detect
    fabrication.
    """
    created = _as_utc(_field(entry, "created_at"))
    if created is None:
        return None
    called = _as_utc(_field(entry, "called_at")) or _as_utc(_field(entry, "started_at"))
    if called is None:
        return None
    minutes = (called - created).total_seconds() / 60.0
    if minutes < 0:
        return None  # clock skew or a bad backfill — not a usable sample
    return minutes


def accuracy_report(
    entries: Iterable[Any] | None,
    tolerance: int = ACCURACY_TOLERANCE_MINUTES,
) -> dict[str, Any]:
    """Compare the wait we PROMISED against the wait we DELIVERED.

    This is the metric the whole EWT engine is accountable to. The blueprint's
    North Star is ±5 minutes; without this number "self-calibrating" is a claim,
    not a fact.

    Reads ``estimated_minutes`` (stamped at booking) and the real
    booking → called gap. Only rows that have both are counted, and ``skipped``
    reports how many were dropped — an accuracy figure computed over a silently
    filtered subset would be worse than no figure at all.

    Returns:
        ``promised_avg``, ``delivered_avg``, ``bias_minutes``, ``mean_abs_error``,
        ``within_tolerance_pct``, ``accuracy_grade``, ``samples``, ``skipped``.

        ``bias_minutes`` is ``mean(delivered − promised)``:

          * **positive** — patients waited *longer* than we told them. We were
            optimistic, which is the failure that costs a patient their trust
            (and sometimes their turn).
          * **negative** — patients waited *less* than we told them. We were
            conservative: a safe error, but one that still needs watching,
            because an over-cautious EWT sends people away for no reason.
    """
    try:
        limit = max(1, int(tolerance))
    except (TypeError, ValueError):
        limit = ACCURACY_TOLERANCE_MINUTES

    pairs: list[tuple[float, float]] = []
    skipped = 0
    for entry in entries or []:
        promised = _field(entry, "estimated_minutes")
        delivered = delivered_wait_minutes(entry)
        if promised is None or delivered is None:
            skipped += 1
            continue
        try:
            promised_value = float(promised)
        except (TypeError, ValueError):
            skipped += 1
            continue
        if promised_value < 0:
            skipped += 1
            continue
        pairs.append((promised_value, float(delivered)))

    if not pairs:
        return {
            "promised_avg": None,
            "delivered_avg": None,
            "bias_minutes": None,
            "mean_abs_error": None,
            "within_tolerance_pct": None,
            "accuracy_grade": "no_data",
            "tolerance_minutes": limit,
            "samples": 0,
            "skipped": skipped,
            "note": "Abhi itna data nahi hai — accuracy report kuch dinon me banegi.",
        }

    count = len(pairs)
    promised_avg = sum(p for p, _ in pairs) / count
    delivered_avg = sum(d for _, d in pairs) / count
    errors = [d - p for p, d in pairs]
    abs_errors = [abs(e) for e in errors]
    mean_abs = sum(abs_errors) / count
    within = sum(1 for e in abs_errors if e <= limit)
    within_pct = round(100.0 * within / count, 1)

    # Grade on the ±tolerance hit rate, not on the mean — one 90-minute
    # outlier should not hide a clinic that is accurate 95% of the time.
    if within_pct >= 80:
        grade = "excellent"
    elif within_pct >= 60:
        grade = "good"
    elif within_pct >= 40:
        grade = "fair"
    else:
        grade = "poor"

    return {
        "promised_avg": round(promised_avg, 1),
        "delivered_avg": round(delivered_avg, 1),
        # positive = patients waited LONGER than promised (we were optimistic)
        # negative = patients waited less (conservative, but still worth seeing)
        "bias_minutes": round(sum(errors) / count, 1),
        "mean_abs_error": round(mean_abs, 1),
        "within_tolerance_pct": within_pct,
        "accuracy_grade": grade,
        "tolerance_minutes": limit,
        "samples": count,
        "skipped": skipped,
        "note": accuracy_note(grade, within_pct, limit, count),
    }


def accuracy_note(grade: str, within_pct: float, tolerance: int, samples: int) -> str:
    """One Hinglish line a clinic owner can act on."""
    if samples < MIN_SAMPLES_FOR_TRUST:
        return (
            f"Sirf {samples} sample — thoda data aur aane dein, phir bharosa kar sakte hain."
        )
    if grade == "excellent":
        return f"{within_pct}% patients ko ±{tolerance} min ke andar sahi wait bata — badhiya."
    if grade == "good":
        return f"{within_pct}% sahi — theek hai, engine khud ko calibrate kar raha hai."
    if grade == "fair":
        return (
            f"Sirf {within_pct}% ±{tolerance} min me — thoda off hai. "
            "Zyada patients ka status update karne se accuracy badhegi."
        )
    return (
        f"Sirf {within_pct}% sahi — wait ka anumaan bharosemand nahi hai. "
        "Zyada tar 'START OPD' aur token complete karne se sudhrega."
    )



# ── The estimate ────────────────────────────────────────────────────────────


def eta_confidence(patients_ahead: int, samples: int) -> str:
    """How much should the patient trust this number?"""
    if samples >= SAMPLES_FOR_HIGH_CONFIDENCE and patients_ahead <= 5:
        return "high"
    if samples >= MIN_SAMPLES_FOR_TRUST and patients_ahead <= 10:
        return "medium"
    return "low"


def estimate_wait(
    ahead: Sequence[Any] | None = None,
    avg_minutes: float = DEFAULT_AVG_MINUTES,
    samples: int = 0,
    current: Any = None,
    chamber_open: bool = True,
    me: Any = None,
    now: datetime | None = None,
    doctor_name: str = "",
    velocity: float = 1.0,
) -> WaitEstimate:
    """The heart of the module — estimate one patient's wait.

    The model, in plain words::

        your wait = everyone still waiting in front of you
                  + what is LEFT of the consultation happening right now
                  + a penalty if that consultation is already overrunning
                  ... all scaled by how fast the chamber is moving today

    Args:
        ahead: entries waiting (WAITING / CALLED / HOLD) — the patient inside
            the chamber must NOT be in this list, or they are counted twice.
        avg_minutes: learned average from :func:`avg_service_minutes`.
        samples: how many consultations that average is based on.
        current: the entry currently IN_PROGRESS, if any.
        chamber_open: False until the doctor presses START OPD (Part D · E-01).
        me: this patient's own entry — a patient already called has burned part
            of their wait live, so we do not count it twice.
        now: injectable clock (tests).
        doctor_name: only used for the note text.
        velocity: recent pace from :func:`recent_velocity` (Part F merge).

    Returns:
        :class:`WaitEstimate` — never raises, always safe to render.
    """
    ahead_list = list(ahead or [])
    waiting_ahead = len(ahead_list)
    patients_ahead = waiting_ahead + (1 if current is not None else 0)
    confirm = float(avg_minutes or DEFAULT_AVG_MINUTES)
    pace = max(MIN_VELOCITY, min(MAX_VELOCITY, float(velocity or 1.0)))

    # ── E-01 chamber gate: no countdown until the doctor is actually in ──
    if not chamber_open:
        who = f"Dr. {doctor_name}" if doctor_name else "Doctor"
        return WaitEstimate(
            minutes=0,
            patients_ahead=patients_ahead,
            avg_service_minutes=round(confirm, 1),
            delay_minutes=0.0,
            confidence="low",
            state="arrival_pending",
            chamber_open=False,
            samples=samples,
            note=f"{who} abhi chamber me nahi aaye — aapka number safe hai.",
            velocity=1.0,
        )

    # Time already consumed by the consultation inside the chamber.
    remaining_current = 0.0
    overrun = 0.0
    if current is not None:
        expected_current = visit_minutes(current, confirm)
        spent_current = elapsed_since_started(current, now=now)
        remaining_current = max(0.0, expected_current - spent_current)
        overrun = min(
            MAX_DELAY_PENALTY_MINUTES, max(0.0, spent_current - expected_current)
        )

    total = sum(visit_minutes(entry, confirm) for entry in ahead_list)
    total += remaining_current
    total *= pace  # today's real pace, not just the long-run average
    total += overrun

    # If this patient was already called they have been waiting live — do not
    # bill them for time that has already passed.
    spent = elapsed_since_called(me, now=now) if me is not None else 0.0
    total -= min(spent, total)

    minutes = int(round(max(0.0, total)))
    if patients_ahead > 0:
        # Never show "0 min" while people are still ahead of you.
        minutes = max(MIN_EWT_MINUTES, minutes)
    minutes = max(0, min(MAX_EWT_MINUTES, minutes))

    note = ""
    if patients_ahead == 0:
        note = "Aapki baari hai."
    elif overrun >= 3:
        note = f"Chamber me case lamba chal raha hai (+{int(round(overrun))} min)."
    elif pace >= 1.2:
        note = "Aaj cases thode lambe chal rahe hain — wait badh sakta hai."
    elif pace <= 0.8:
        note = "Chamber tez chal raha hai — jaldi number aa sakta hai."

    return WaitEstimate(
        minutes=minutes,
        patients_ahead=patients_ahead,
        avg_service_minutes=round(confirm, 1),
        delay_minutes=round(overrun, 1),
        confidence=eta_confidence(patients_ahead, samples),
        state="live",
        chamber_open=True,
        samples=samples,
        note=note,
        velocity=round(pace, 2),
    )


# ── Snapshot persistence (booking time) ─────────────────────────────────────


def booking_snapshot(
    estimate: WaitEstimate,
    visit_type: str,
) -> dict[str, Any]:
    """Columns to stamp onto a newly booked queue entry.

    Storing the estimate at booking time lets us later compare *promised* vs
    *delivered* wait — that is the EWT accuracy metric from the blueprint.
    """
    return {
        "visit_type": visit_type,
        "complexity_weight": complexity_weight(visit_type),
        "estimated_minutes": int(estimate.minutes),
    }


# ── Delay badge for staff screens ───────────────────────────────────────────


def delay_severity(
    current: Any, avg_minutes: float, now: datetime | None = None
) -> str:
    """🟡 / 🔴 badge level for the doctor's live view (warning 5, critical 10)."""
    delay = live_delay_minutes(current, avg_minutes, now=now)
    if delay >= 10:
        return "critical"
    if delay >= 5:
        return "warning"
    return "none"


def ewt_feed_line(entry: Any, estimate: WaitEstimate) -> dict[str, Any]:
    """Compact row for the doctor's live EWT feed."""
    return {
        "entry_id": str(_field(entry, "id", "") or ""),
        "token_number": _field(entry, "token_number", 0),
        "patient_name": _field(entry, "patient_name", "") or "",
        "visit_type": _field(entry, "visit_type", "") or "",
        "visit_label": VISIT_TYPE_LABEL.get(
            (_field(entry, "visit_type", "") or "").lower(), "Consultation"
        ),
        "wait_minutes": estimate.minutes,
        "confidence": estimate.confidence,
    }
