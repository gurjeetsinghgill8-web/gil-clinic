"""Find a Doctor — public city marketplace routes.

Turns the multi-tenant `clinics` registry into a patient-facing directory
with a two-tier ranking:

    Tier 1  — partner clinics (active SaaS license)  → "LIVE QUEUE ACTIVE"
    Tier 2  — directory-only clinics (license inactive/expired) → "call directly"

End-to-end (real data):
    GET  /find-doctor                        → patient-facing HTML marketplace
    GET  /api/v1/marketplace/meta            → distinct cities + specialties
    GET  /api/v1/marketplace/doctors         → directory + REAL live queue depth
    POST /api/v1/marketplace/book            → 1-tap booking (creates a real
                                               OPD queue entry + tracking link)

This is deliberately public (no login) because finding a doctor must never
require an account. Only safe, non-sensitive clinic fields are returned.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from src.domain.clinic import opening_hours
from src.domain.queue import ewt
from src.infrastructure.clinic.models.clinic_model import ClinicModel
from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel
from src.shared.infrastructure.database import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Marketplace"])

_TEMPLATES_DIR = Path(__file__).parents[4] / "templates"

# ── SPECIALTY KEYWORD MAP ──────────────────────────────────────────────────
# Plain-language problems (Hindi + English) → specialty. Kept in one place so
# the UI and the API stay in sync.
PROBLEM_TO_SPECIALTY: dict[str, str] = {
    "chest pain": "Cardiology", "seene": "Cardiology", "dil": "Cardiology",
    "heart": "Cardiology", "bp": "Cardiology", "blood pressure": "Cardiology",
    "ghabrahat": "Cardiology", "palpitation": "Cardiology",
    "fever": "General Physician", "bukhar": "General Physician", "cough": "General Physician",
    "khansi": "General Physician", "cold": "General Physician", "sardi": "General Physician",
    "sugar": "General Physician", "diabetes": "General Physician", "madhu": "General Physician",
    "headache": "General Physician", "sir dard": "General Physician",
    "bone": "Orthopedics", "haddi": "Orthopedics", "joint": "Orthopedics",
    "knee": "Orthopedics", "ghutna": "Orthopedics", "back pain": "Orthopedics",
    "kamardard": "Orthopedics", "fracture": "Orthopedics",
    "child": "Pediatrics", "bachcha": "Pediatrics", "bacha": "Pediatrics",
    "baby": "Pediatrics", "kids": "Pediatrics",
    "skin": "Dermatology", "twacha": "Dermatology", "dane": "Dermatology",
    "hair": "Dermatology",
    "eye": "Ophthalmology", "aankh": "Ophthalmology", "nazar": "Ophthalmology",
    "ear": "ENT", "kaan": "ENT", "nose": "ENT", "naak": "ENT", "gala": "ENT",
    "throat": "ENT",
    "teeth": "Dental", "daant": "Dental", "tooth": "Dental",
    "pregnan": "Gynecology", "ladies": "Gynecology", "stree": "Gynecology",
    "mahila": "Gynecology", "women": "Gynecology",
    "stomach": "Gastroenterology", "pet": "Gastroenterology", "gas": "Gastroenterology",
    "acidity": "Gastroenterology", "digest": "Gastroenterology",
}

# Fallback minutes per OPD patient when a clinic has no consultation history at
# all. The real number now comes from the EWT engine (`src/domain/queue/ewt.py`),
# which learns each doctor's actual average — this constant is only the cold-start
# default and is kept so old call sites keep working.
MINUTES_PER_PATIENT = 7

# ── Demo clinics (marketplace ko turant "alive" dikhane ke liye) ─────────────
# Idempotent seed — clinic_code se dedupe. Admin panel se edit/delete kar sakte hain.
DEMO_CLINICS = [
    ("DEMO-001", "Gill Heart & Multispeciality Clinic", "G.S. Gill", "MD, DM (Cardiology)",
     "Cardiology", "Jodhpur", "Rajasthan", 26.2389, 73.0243, "9829012345"),
    ("DEMO-002", "Sharma Family Clinic", "Anita Sharma", "MBBS, MD (Medicine)",
     "General Physician", "Jodhpur", "Rajasthan", 26.2700, 73.0200, "9829023456"),
    ("DEMO-003", "Gupta Ortho & Joint Care", "Ramesh Gupta", "MS (Orthopedics)",
     "Orthopedics", "Jaipur", "Rajasthan", 26.9124, 75.7873, "9829034567"),
    ("DEMO-004", "Verma Child Care", "Priya Verma", "MD (Pediatrics)",
     "Pediatrics", "Jaipur", "Rajasthan", 26.9100, 75.7900, "9829045678"),
    ("DEMO-005", "Mehta Skin & Hair Clinic", "Arjun Mehta", "MD (Dermatology)",
     "Dermatology", "Ahmedabad", "Gujarat", 23.0225, 72.5714, "9829056789"),
    ("DEMO-006", "Rao Women's Wellness", "Sunita Rao", "MS (Gynecology)",
     "Gynecology", "Ahmedabad", "Gujarat", 23.0300, 72.5800, "9829067890"),
    ("DEMO-007", "Patel General Clinic", "Karan Patel", "MBBS, MD",
     "General Physician", "Delhi", "Delhi", 28.6139, 77.2090, "9829078901"),
    ("DEMO-008", "Singh Cardiac Centre", "Neha Singh", "MD, DM (Cardiology)",
     "Cardiology", "Delhi", "Delhi", 28.6200, 77.2100, "9829089012"),
]

SEED_TOKEN = "GIL-DEMO-SEED-2026"

#: Which doctor's chamber a public booking lands in. The OPD session layer uses
#: "chief" / "junior" doctor ids; a public booking always targets the clinic's
#: primary doctor. One constant so queue partitioning stays consistent
#: everywhere (Part D · E-04).
BOOKING_DOCTOR_ID = "chief"


def _opd_room_name() -> str:
    """Chamber name for OPD from the dynamic service config (BUG-02).

    Bookings used to store an empty room, so the doctor's screen showed no
    chamber at all. Falls back to a sane label if the provider is unavailable.
    """
    try:
        from src.infrastructure.clinic.department_provider import get_service_by_code

        svc = get_service_by_code("OPD")
        room = getattr(svc, "room_name", "") if svc else ""
        if room:
            return str(room)
    except Exception:  # pragma: no cover - provider is best-effort
        pass
    return "OPD Room"


def _booking_message(
    token: int,
    patient_name: str,
    clinic_name: str,
    ahead: int,
    minutes: int,
    state: str,
) -> str:
    """Patient-facing confirmation — honest when the doctor has not arrived."""
    if state == "arrival_pending":
        return (
            f"Token #{token} booked for {patient_name} at {clinic_name}. "
            "Doctor abhi chamber me nahi aaye — aapka number safe hai, "
            "wait count OPD shuru hote hi chalega."
        )
    return (
        f"Token #{token} booked for {patient_name} at {clinic_name}. "
        f"{ahead} patient(s) ahead — est. {minutes} min."
    )


def _detect_specialty(problem: str | None) -> str | None:
    """Map a plain-language problem to a specialty, or return None."""
    if not problem:
        return None
    haystack = problem.lower()
    for keyword, specialty in PROBLEM_TO_SPECIALTY.items():
        if keyword in haystack:
            return specialty
    return None


# ── REAL LIVE QUEUE + EWT (end-to-end) ─────────────────────────────────────
# Reads the actual queue_entries table — never a demo number:
#   * active rows  → who is waiting, and who is inside the chamber right now
#   * 30-day history → the doctor's REAL average consultation length
#   * chamber_sessions → did the doctor press ▶ START OPD today? (Part D · E-01)
# The wait is then computed by `src/domain/queue/ewt.py` instead of the old
# flat "patients × 7 minutes" guess.
async def _queue_map(clinic_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Return live queue + EWT data for each clinic."""
    out: dict[str, dict[str, Any]] = {}
    if not clinic_ids:
        return out
    try:
        from src.infrastructure.queue.models.chamber_session_model import (
            ChamberSessionModel,
        )

        now = datetime.now(timezone.utc)
        today = now.date()
        history_since = now - timedelta(days=30)

        async with async_session_factory() as session:
            active_rows = (
                await session.execute(
                    sa.select(QueueEntryModel).where(
                        QueueEntryModel.clinic_id.in_(clinic_ids),
                        QueueEntryModel.completed_at.is_(None),
                        QueueEntryModel.delivered_at.is_(None),
                        QueueEntryModel.service_code == "OPD",
                        QueueEntryModel.status.notin_(("CANCELLED", "NO_SHOW")),
                    )
                )
            ).scalars().all()

            history_rows = (
                await session.execute(
                    sa.select(
                        QueueEntryModel.clinic_id,
                        QueueEntryModel.started_at,
                        QueueEntryModel.completed_at,
                    )
                    .where(
                        QueueEntryModel.clinic_id.in_(clinic_ids),
                        QueueEntryModel.service_code == "OPD",
                        QueueEntryModel.completed_at.is_not(None),
                        QueueEntryModel.completed_at >= history_since,
                    )
                    # oldest → newest: recent_velocity() only reads the tail
                    .order_by(QueueEntryModel.completed_at.asc())
                    .limit(2000)
                )
            ).all()

            chamber_rows = (
                await session.execute(
                    sa.select(ChamberSessionModel).where(
                        ChamberSessionModel.clinic_id.in_(clinic_ids),
                        ChamberSessionModel.session_date == today,
                    )
                )
            ).scalars().all()
    except Exception as e:  # pragma: no cover - defensive (older DBs)
        logger.warning("marketplace queue map failed: %s", e)
        return out

    # ── group the active rows per clinic ──
    buckets: dict[str, dict[str, Any]] = {}
    for entry in active_rows:
        cid = str(entry.clinic_id)
        bucket = buckets.setdefault(cid, {"waiting": [], "current": None, "active": []})
        bucket["active"].append(entry)
        if (entry.status or "").upper() == "IN_PROGRESS":
            if bucket["current"] is None:
                bucket["current"] = entry
        else:
            bucket["waiting"].append(entry)

    history: dict[str, list[Any]] = {}
    for cid, started_at, completed_at in history_rows:
        history.setdefault(str(cid), []).append(
            {"started_at": started_at, "completed_at": completed_at}
        )

    # Chamber gate: a clinic that has never used chamber sessions keeps the old
    # behaviour (open) so nothing regresses; a clinic that HAS started tracking
    # is gated honestly on whether the doctor actually opened the chamber.
    chamber_open: dict[str, bool] = {}
    for row in chamber_rows:
        cid = str(row.clinic_id)
        chamber_open[cid] = bool(chamber_open.get(cid)) or row.is_open

    for cid in clinic_ids:
        bucket = buckets.get(cid, {"waiting": [], "current": None, "active": []})
        history_rows_for_clinic = history.get(cid, [])
        avg_minutes, samples = ewt.avg_service_minutes(history_rows_for_clinic)
        pace = ewt.recent_velocity(history_rows_for_clinic, avg_minutes)
        tracked = cid in chamber_open
        is_open = chamber_open.get(cid, True)

        estimate = ewt.estimate_wait(
            ahead=bucket["waiting"],
            avg_minutes=avg_minutes,
            samples=samples,
            current=bucket["current"],
            chamber_open=is_open,
            velocity=pace,
        )
        tokens = [e.token_number for e in bucket["active"] if e.token_number]
        out[cid] = {
            "patients_ahead": estimate.patients_ahead,
            "serving_token": max(tokens) if tokens else 0,
            "wait_minutes": estimate.minutes,
            "confidence": estimate.confidence,
            "state": estimate.state,
            "chamber_open": is_open,
            "chamber_tracked": tracked,
            "avg_minutes": estimate.avg_service_minutes,
            "samples": samples,
            "velocity": estimate.velocity,
            "delay_minutes": int(round(estimate.delay_minutes)),
            "note": estimate.note,
        }
    return out


def _to_public(
    clinic: ClinicModel,
    queue: dict[str, Any] | None,
    lat: float | None = None,
    lon: float | None = None,
) -> dict[str, Any]:
    """Project a ClinicModel row into a safe, public JSON shape."""
    partner = bool(clinic.is_license_active and clinic.is_active)
    live: dict[str, Any] | None = None
    if partner:
        q = queue or {}
        ahead = int(q.get("patients_ahead") or 0)
        serving = int(q.get("serving_token") or 0)
        wait_minutes = q.get("wait_minutes")
        chamber_open = bool(q.get("chamber_open", True))
        live = {
            "serving_token": serving,
            "patients_ahead": ahead,
            # EWT engine output (self-calibrating), not a flat guess.
            "wait_minutes": int(wait_minutes) if wait_minutes is not None else ahead * MINUTES_PER_PATIENT,
            "confidence": q.get("confidence") or "low",
            "state": q.get("state") or "live",
            "chamber_open": chamber_open,
            "chamber": "OPD",
            "avg_minutes": q.get("avg_minutes"),
            "velocity": q.get("velocity"),
            "delay_minutes": int(q.get("delay_minutes") or 0),
            "note": q.get("note") or "",
            "real": True,
        }

    distance_km = None
    if lat is not None and lon is not None and clinic.latitude is not None and clinic.longitude is not None:
        distance_km = round(_haversine(lat, lon, float(clinic.latitude), float(clinic.longitude)), 1)

    # ── Real availability (AVL-02 / E-06) ──
    # Used to be the static string "OPEN" for every licensed clinic, which is
    # how a patient ended up outside a closed shutter at 10 PM on a Sunday.
    avail = opening_hours.to_public_dict(
        open_time=getattr(clinic, "open_time", None),
        close_time=getattr(clinic, "close_time", None),
        closed_days=getattr(clinic, "closed_days", None),
        holiday_until=getattr(clinic, "holiday_until", None),
        is_partner=partner,
    )
    # Schedule-only truth, independent of tier — what the 🟢 filter uses.
    schedule_open = opening_hours.within_hours(
        open_time=getattr(clinic, "open_time", None),
        close_time=getattr(clinic, "close_time", None),
        closed_days=getattr(clinic, "closed_days", None),
        holiday_until=getattr(clinic, "holiday_until", None),
    )

    return {
        "id": str(clinic.id),
        "clinic_name": clinic.clinic_name or "",
        "doctor_name": clinic.doctor_name or "",
        "degree": (clinic.doctor_degree or "").strip() or "MBBS",
        "specialty": (clinic.specialty or "General Physician").strip() or "General Physician",
        "city": (clinic.city or "").strip(),
        "state": (clinic.state or "").strip(),
        "address": (clinic.address or "").strip(),
        "phone": (clinic.doctor_phone or "").strip(),
        "partner": partner,
        "tier": 1 if partner else 2,
        # Open for real today: OPEN / CLOSING_SOON / CLOSED / HOLIDAY / DIRECTORY.
        "availability": avail["state"],
        "availability_label": avail["label"],
        "availability_badge": avail["badge"],
        "is_open_now": avail["is_open"],
        "within_hours": schedule_open,
        "hours": avail["hours"],
        "open_time": avail["open_time"],
        "close_time": avail["close_time"],
        "next_opening": avail["next_opening"],
        "closing_note": avail["closing_note"],
        "rating": round(float(clinic.rating), 1) if getattr(clinic, "rating", None) else None,
        "rating_count": int(getattr(clinic, "rating_count", 0) or 0),
        "live": live,
        "distance_km": distance_km,
    }


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    import math

    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@router.get("/api/v1/marketplace/meta")
async def marketplace_meta():
    """Distinct cities + specialties for the filter UI."""
    cities: list[str] = []
    specialties: list[str] = []
    try:
        async with async_session_factory() as session:
            city_rows = await session.execute(
                sa.select(ClinicModel.city)
                .where(ClinicModel.is_active == True)  # noqa: E712
                .distinct()
                .order_by(ClinicModel.city)
            )
            cities = sorted({r[0].strip() for r in city_rows if r[0] and r[0].strip()})
            spec_rows = await session.execute(
                sa.select(ClinicModel.specialty)
                .where(ClinicModel.is_active == True)  # noqa: E712
                .distinct()
                .order_by(ClinicModel.specialty)
            )
            specialties = sorted({r[0].strip() for r in spec_rows if r[0] and r[0].strip()})
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("marketplace meta query failed: %s", e)

    if not specialties:
        specialties = [
            "Cardiology", "General Physician", "Orthopedics", "Pediatrics",
            "Dermatology", "Gynecology", "ENT", "Ophthalmology", "Dental",
        ]
    return {"cities": cities, "specialties": specialties}


#: Sort keys the public directory accepts. Anything else falls back to "smart".
SORT_KEYS = ("smart", "distance", "wait", "rating", "name")


def _sort_key(sort: str, doctor: dict[str, Any]) -> Any:
    """Secondary ordering inside one tier, per the requested sort key.

    ``None`` must never be compared with a number, so every key returns a
    tuple whose first element is the "is this known?" flag — unknown values
    sort last instead of crashing the request.
    """
    live = doctor.get("live") or {}
    wait = live.get("wait_minutes")
    distance = doctor.get("distance_km")
    rating = doctor.get("rating")

    if sort == "distance":
        return (distance is None, distance if distance is not None else 0.0,
                doctor.get("doctor_name") or "")
    if sort == "wait":
        # Clinics whose chamber is not open yet show no countdown — rank them
        # after the ones with a real number rather than pretending they are 0.
        known = wait is not None and live.get("state") == "live"
        return (not known, int(wait) if known else 0,
                distance if distance is not None else 9999.0,
                doctor.get("doctor_name") or "")
    if sort == "rating":
        return (rating is None, -(rating or 0.0), doctor.get("doctor_name") or "")
    if sort == "name":
        return (doctor.get("doctor_name") or "").lower()

    # smart: open first, then the shortest real wait, then nearest, then rated.
    return (
        0 if doctor.get("is_open_now") else 1,
        live.get("wait_minutes") if live.get("wait_minutes") is not None else 9999,
        distance if distance is not None else 9999.0,
        -(rating or 0.0),
        (doctor.get("doctor_name") or "").lower(),
    )


@router.get("/api/v1/marketplace/doctors")
async def marketplace_doctors(
    city: str | None = Query(default=None),
    specialty: str | None = Query(default=None),
    problem: str | None = Query(default=None),
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
    open_now: bool | None = Query(default=None),
    sort: str = Query(default="smart"),
):
    """Public doctor directory with city / specialty / plain-language filters.

    Ranking: partner clinics (active license) always first, then directory
    listings — the documented two-tier rule. **Within** a tier the requested
    ``sort`` decides:

        smart (default) · distance · wait · rating · name

    ``open_now=true`` keeps only clinics whose stated hours cover right now
    (AVL-02), so a patient is not sent to a closed shutter.
    """
    resolved_specialty = _detect_specialty(problem) or specialty
    wanted_sort = (sort or "smart").strip().lower()
    if wanted_sort not in SORT_KEYS:
        wanted_sort = "smart"

    doctors: list[dict[str, Any]] = []
    note: str | None = None
    try:
        async with async_session_factory() as session:
            stmt = sa.select(ClinicModel).where(ClinicModel.is_active == True)  # noqa: E712
            if city:
                stmt = stmt.where(sa.func.lower(ClinicModel.city) == city.strip().lower())
            if resolved_specialty:
                stmt = stmt.where(
                    sa.func.lower(ClinicModel.specialty) == resolved_specialty.strip().lower()
                )
            stmt = stmt.order_by(
                ClinicModel.is_license_active.desc(),
                ClinicModel.doctor_name.asc(),
            )
            rows = (await session.execute(stmt)).scalars().all()
            queue = await _queue_map([str(c.id) for c in rows])
            doctors = [_to_public(c, queue.get(str(c.id)), lat, lon) for c in rows]
    except Exception as e:  # pragma: no cover - defensive
        logger.exception("marketplace doctors query failed")
        note = f"Directory temporarily unavailable ({type(e).__name__}). Please try again."

    total_before_filter = len(doctors)

    if open_now:
        doctors = [d for d in doctors if d.get("within_hours")]

    if wanted_sort == "smart" or wanted_sort in SORT_KEYS:
        # Tier first (1 = partner), then the chosen key. Stable, so the SQL
        # ordering still breaks exact ties deterministically.
        doctors.sort(key=lambda d: (d.get("tier", 2), _sort_key(wanted_sort, d)))

    if open_now and not doctors:
        note = note or "Abhi koi clinic khuli nahi hai — filter hata kar dekhein."

    return {
        "doctors": doctors,
        "total": len(doctors),
        "total_before_filter": total_before_filter,
        "partners": sum(1 for d in doctors if d["tier"] == 1),
        "open_now": sum(1 for d in doctors if d.get("is_open_now")),
        "resolved_specialty": resolved_specialty,
        "sort": wanted_sort,
        "note": note,
    }


@router.post("/api/v1/marketplace/book")
async def marketplace_book(request: Request):
    """1-tap booking — creates a REAL OPD queue entry for the clinic.

    Body: {clinic_id, name, phone, problem?, specialty?}
    Returns the token number + a live tracking link the patient can open.
    """
    from src.infrastructure.patient.models.patient_model import PatientModel
    from src.shared.domain.base_entity import uuid7

    try:
        body = await request.json()
    except Exception:
        body = {}

    clinic_id = str(body.get("clinic_id") or "").strip()
    name = str(body.get("name") or "").strip()
    phone = str(body.get("phone") or "").strip()
    complaints = str(body.get("problem") or "").strip()
    # Age is optional; it used to be hardcoded to 30, which quietly defeated any
    # age-based logic downstream. Unknown age still defaults to 30.
    try:
        age = int(body.get("age")) if str(body.get("age") or "").strip() else 30
    except (TypeError, ValueError):
        age = 30
    if age < 0 or age > 130:
        age = 30
    if not clinic_id or not name:
        return JSONResponse({"ok": False, "error": "Clinic aur patient name chahiye."}, status_code=400)
    if phone and len(phone) < 10:
        return JSONResponse({"ok": False, "error": "10-digit phone number chahiye."}, status_code=400)

    try:
        clinic_uuid = uuid.UUID(clinic_id)
    except (ValueError, AttributeError, TypeError):
        return JSONResponse({"ok": False, "error": "Clinic nahi mila."}, status_code=404)

    now = datetime.now(timezone.utc)
    date_prefix = now.strftime("%Y%m%d")
    phone_hash = hashlib.sha256(phone.encode()).hexdigest() if phone else ""

    async with async_session_factory() as session:
        clinic = await session.get(ClinicModel, clinic_uuid)
        if clinic is None or not clinic.is_active:
            return JSONResponse({"ok": False, "error": "Clinic nahi mila."}, status_code=404)

        # ── EWT snapshot BEFORE this booking joins the queue ──
        # This is what we promise the patient; it is stored on the row so we can
        # later compare promised vs delivered wait (the accuracy metric).
        queue_info = (await _queue_map([str(clinic.id)])).get(str(clinic.id), {})
        promised_minutes = int(queue_info.get("wait_minutes") or 0)
        promised_state = queue_info.get("state") or "live"
        promised_note = queue_info.get("note") or ""

        # ── patient: reuse by phone, else create ──
        existing = None
        if phone:
            # A family can share one phone number, so this must NEVER use
            # scalar_one_or_none() — that raises MultipleResultsFound and turns
            # booking into a 500. Most recent record wins.
            row = await session.execute(
                sa.select(PatientModel)
                .where(PatientModel.phone_hash == phone_hash)
                .order_by(PatientModel.created_at.desc())
                .limit(1)
            )
            existing = row.scalars().first()

        if existing is not None:
            patient_id = existing.patient_id
            patient_uuid = str(existing.id)
            patient_name = existing.name
            existing.total_visits = (existing.total_visits or 0) + 1
            existing.last_visit_at = now
            total_visits = int(existing.total_visits or 1)
        else:
            seq_row = await session.execute(
                sa.select(sa.func.count(PatientModel.id)).where(
                    PatientModel.patient_id.like(f"CQ-{date_prefix}-%")
                )
            )
            seq = (seq_row.scalar() or 0) + 1
            patient_id = f"CQ-{date_prefix}-{seq:03d}"
            patient_uuid_obj = uuid7()
            patient_uuid = str(patient_uuid_obj)
            patient_name = name
            total_visits = 1
            patient = PatientModel(
                id=patient_uuid_obj,
                patient_id=patient_id,
                name=name,
                age=age,
                gender="Not Specified",
                date_of_birth="",
                phone=phone,
                phone_hash=phone_hash,
                address="",
                status="active",
                total_visits=1,
                last_visit_at=now,
                reception_inquiry=complaints,
                version=1,
                created_at=now,
                updated_at=now,
            )
            session.add(patient)

        # ── next OPD token, partitioned PER CLINIC (BUG-01) ──
        # The old query had no clinic filter, so two different clinics booking
        # on the same day shared one token sequence (clinic A #17, clinic B #18).
        token_row = await session.execute(
            sa.select(sa.func.coalesce(sa.func.max(QueueEntryModel.token_number), 0)).where(
                QueueEntryModel.clinic_id == str(clinic.id),
                QueueEntryModel.doctor_id == BOOKING_DOCTOR_ID,
                QueueEntryModel.service_code == "OPD",
                QueueEntryModel.visit_id.like(f"VIS-{date_prefix}-%"),
            )
        )
        token = (token_row.scalar() or 0) + 1

        # ── visit classification + chamber room (BUG-02) ──
        visit_type = ewt.classify_visit_type(total_visits=total_visits, age=age)
        room = _opd_room_name()
        department = (clinic.specialty or "").strip() or "OPD"

        visit_id = f"VIS-{date_prefix}-{uuid7().hex[:6]}"
        entry = QueueEntryModel(
            id=uuid7(),
            clinic_id=str(clinic.id),
            doctor_id=BOOKING_DOCTOR_ID,
            visit_id=visit_id,
            patient_id=patient_id,
            patient_uuid=patient_uuid,
            patient_name=patient_name,
            service_code="OPD",
            token_number=token,
            department=department,
            room=room,
            status="WAITING",
            priority=0,
            display_order=0,
            sort_key=float(token),
            visit_type=visit_type,
            complexity_weight=ewt.complexity_weight(visit_type),
            estimated_minutes=promised_minutes,
            notes=complaints or "",
            created_by="marketplace",
            updated_by="marketplace",
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(entry)
        await session.commit()

        ahead = int(queue_info.get("patients_ahead") or 0)

    # ── live tracking link (same one the clinic reception uses) ──
    tracking_url = ""
    try:
        from src.presentation.staff.routes.staff_routes import make_tracking_token
        from src.utils.public_url import public_base_url

        tracking_url = f"{public_base_url(request)}/track/{make_tracking_token(patient_id)}"
    except Exception:  # pragma: no cover
        tracking_url = ""

    return JSONResponse(
        {
            "ok": True,
            "token": token,
            "patients_ahead": ahead,
            "wait_minutes": promised_minutes,
            "wait_state": promised_state,
            "wait_note": promised_note,
            "visit_type": visit_type,
            "visit_label": ewt.VISIT_TYPE_LABEL.get(visit_type, "Consultation"),
            "room": room,
            "visit_id": visit_id,
            "patient_id": patient_id,
            "clinic_name": clinic.clinic_name,
            "doctor_name": clinic.doctor_name,
            "tracking_url": tracking_url,
            "message": _booking_message(
                token=token,
                patient_name=patient_name,
                clinic_name=clinic.clinic_name or "",
                ahead=ahead,
                minutes=promised_minutes,
                state=promised_state,
            ),
        }
    )


@router.post("/seed", include_in_schema=False)
async def seed_demo_clinics(token: str = Query("")):
    """One-time demo clinics seed — idempotent (clinic_code se dedupe).

    Token-gated: `POST /api/v1/marketplace/seed?token=GIL-DEMO-SEED-2026`
    Demo clinics admin panel se edit/delete kar sakte hain.
    """
    if token != SEED_TOKEN:
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
    created = 0
    skipped = 0
    async with async_session_factory() as session:
        for code, cname, dname, degree, spec, city, state, lat, lon, phone in DEMO_CLINICS:
            row = await session.execute(
                sa.select(ClinicModel).where(ClinicModel.clinic_code == code)
            )
            if row.scalar_one_or_none() is not None:
                skipped += 1
                continue
            session.add(
                ClinicModel(
                    clinic_name=cname,
                    clinic_code=code,
                    doctor_name=dname,
                    doctor_degree=degree,
                    doctor_phone=phone,
                    specialty=spec,
                    city=city,
                    state=state,
                    address=f"{city}, {state}",
                    latitude=lat,
                    longitude=lon,
                    is_license_active=True,
                    is_active=True,
                    created_by="demo_seed",
                )
            )
            created += 1
        await session.commit()
    return JSONResponse({"ok": True, "created": created, "skipped": skipped})


@router.get("/find-doctor", include_in_schema=False)
@router.get("/doctors", include_in_schema=False)
async def find_doctor_page():
    """Patient-facing 'Find a Doctor' marketplace HTML."""
    import jinja2

    loader = jinja2.FileSystemLoader(str(_TEMPLATES_DIR))
    env = jinja2.Environment(loader=loader, auto_reload=True)
    return HTMLResponse(content=env.get_template("marketplace.html").render())
