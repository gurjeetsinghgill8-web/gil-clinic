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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

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

# Average minutes per OPD patient — used to turn "patients ahead" into EWT.
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


def _detect_specialty(problem: str | None) -> str | None:
    """Map a plain-language problem to a specialty, or return None."""
    if not problem:
        return None
    haystack = problem.lower()
    for keyword, specialty in PROBLEM_TO_SPECIALTY.items():
        if keyword in haystack:
            return specialty
    return None


# ── REAL LIVE QUEUE (end-to-end) ───────────────────────────────────────────
# Reads the actual queue_entries table: "patients ahead" = active OPD entries
# for a clinic (not yet completed/delivered); "serving token" = the highest
# active OPD token (the one currently being worked). No fake numbers.
async def _queue_map(clinic_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Return {clinic_id: {patients_ahead, serving_token}} for active OPD queues."""
    out: dict[str, dict[str, Any]] = {}
    if not clinic_ids:
        return out
    try:
        async with async_session_factory() as session:
            rows = await session.execute(
                sa.select(
                    QueueEntryModel.clinic_id,
                    sa.func.count(QueueEntryModel.id),
                    sa.func.max(QueueEntryModel.token_number),
                )
                .where(
                    QueueEntryModel.clinic_id.in_(clinic_ids),
                    QueueEntryModel.completed_at.is_(None),
                    QueueEntryModel.delivered_at.is_(None),
                    QueueEntryModel.service_code == "OPD",
                )
                .group_by(QueueEntryModel.clinic_id)
            )
            for clinic_id, cnt, max_token in rows.all():
                out[str(clinic_id)] = {
                    "patients_ahead": int(cnt or 0),
                    "serving_token": int(max_token or 0),
                }
    except Exception as e:  # pragma: no cover - defensive (older DBs)
        logger.warning("marketplace queue map failed: %s", e)
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
        live = {
            "serving_token": serving,
            "patients_ahead": ahead,
            "wait_minutes": ahead * MINUTES_PER_PATIENT,
            "chamber": "OPD",
            "real": True,
        }

    distance_km = None
    if lat is not None and lon is not None and clinic.latitude is not None and clinic.longitude is not None:
        distance_km = round(_haversine(lat, lon, float(clinic.latitude), float(clinic.longitude)), 1)

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
        "availability": "OPEN" if partner else "DIRECTORY",
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


@router.get("/api/v1/marketplace/doctors")
async def marketplace_doctors(
    city: str | None = Query(default=None),
    specialty: str | None = Query(default=None),
    problem: str | None = Query(default=None),
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
):
    """Public doctor directory with city / specialty / plain-language filters.

    Ranking: partner clinics (active license) always first, then directory
    listings. Live queue depth is read from the real `queue_entries` table.
    """
    resolved_specialty = _detect_specialty(problem) or specialty

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

    return {
        "doctors": doctors,
        "total": len(doctors),
        "partners": sum(1 for d in doctors if d["tier"] == 1),
        "resolved_specialty": resolved_specialty,
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

        # ── patient: reuse by phone, else create ──
        existing = None
        if phone:
            row = await session.execute(
                sa.select(PatientModel).where(PatientModel.phone_hash == phone_hash)
            )
            existing = row.scalar_one_or_none()

        if existing is not None:
            patient_id = existing.patient_id
            patient_uuid = str(existing.id)
            patient_name = existing.name
            existing.total_visits = (existing.total_visits or 0) + 1
            existing.last_visit_at = now
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
            patient = PatientModel(
                id=patient_uuid_obj,
                patient_id=patient_id,
                name=name,
                age=30,
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

        # ── next OPD token for this clinic's OPD queue ──
        token_row = await session.execute(
            sa.select(sa.func.coalesce(sa.func.max(QueueEntryModel.token_number), 0)).where(
                QueueEntryModel.service_code == "OPD",
                QueueEntryModel.visit_id.like(f"VIS-{date_prefix}-%"),
            )
        )
        token = (token_row.scalar() or 0) + 1

        visit_id = f"VIS-{date_prefix}-{uuid7().hex[:6]}"
        entry = QueueEntryModel(
            id=uuid7(),
            clinic_id=str(clinic.id),
            visit_id=visit_id,
            patient_id=patient_id,
            patient_uuid=patient_uuid,
            patient_name=patient_name,
            service_code="OPD",
            token_number=token,
            department="OPD",
            room="",
            status="WAITING",
            priority=0,
            display_order=0,
            notes=complaints or "",
            created_by="marketplace",
            updated_by="marketplace",
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(entry)
        await session.commit()

        ahead_row = await session.execute(
            sa.select(sa.func.count(QueueEntryModel.id)).where(
                QueueEntryModel.clinic_id == str(clinic.id),
                QueueEntryModel.completed_at.is_(None),
                QueueEntryModel.delivered_at.is_(None),
                QueueEntryModel.service_code == "OPD",
                QueueEntryModel.token_number < token,
            )
        )
        ahead = int(ahead_row.scalar() or 0)

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
            "wait_minutes": ahead * MINUTES_PER_PATIENT,
            "visit_id": visit_id,
            "patient_id": patient_id,
            "clinic_name": clinic.clinic_name,
            "doctor_name": clinic.doctor_name,
            "tracking_url": tracking_url,
            "message": (
                f"Token #{token} booked for {patient_name} at {clinic.clinic_name}. "
                f"{ahead} patient(s) ahead — est. {ahead * MINUTES_PER_PATIENT} min."
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
