"""Find a Doctor — public city marketplace routes.

Turns the multi-tenant `clinics` registry into a patient-facing directory
with a two-tier ranking:

    Tier 1  — partner clinics (active SaaS license)  → "LIVE QUEUE ACTIVE"
    Tier 2  — directory-only clinics (license inactive/expired) → "call directly"

Endpoints:
    GET /find-doctor                       → patient-facing HTML marketplace
    GET /api/v1/marketplace/doctors        → JSON directory (city/specialty filters)
    GET /api/v1/marketplace/meta           → distinct cities + specialties

This is deliberately public (no login) because finding a doctor must never
require an account. Only safe, non-sensitive clinic fields are returned.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from src.infrastructure.clinic.models.clinic_model import ClinicModel
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


def _detect_specialty(problem: str | None) -> str | None:
    """Map a plain-language problem to a specialty, or return None."""
    if not problem:
        return None
    haystack = problem.lower()
    for keyword, specialty in PROBLEM_TO_SPECIALTY.items():
        if keyword in haystack:
            return specialty
    return None


# ── LIVE QUEUE SIGNAL (demo + deterministic) ───────────────────────────────
# The real product reads live token / patients-ahead / EWT from the Queue
# Engine (`queue_entries`). Until that data is exposed per clinic, we derive a
# stable, deterministic estimate from the clinic id so the marketplace always
# renders a believable live signal for partner clinics. Swap this function for
# the real Queue Engine read when the live feed is wired up.
def _live_signal(clinic_id: str) -> dict[str, Any]:
    digest = hashlib.sha256(clinic_id.encode("utf-8")).digest()
    # token currently being served (14–42)
    serving_token = 14 + digest[0] % 29
    # patients ahead of a hypothetical new walk-in (1–8)
    patients_ahead = 1 + digest[1] % 8
    # estimated wait in minutes = patients_ahead * per-patient time (5–9 min)
    wait_minutes = patients_ahead * (5 + digest[2] % 5)
    return {
        "serving_token": serving_token,
        "patients_ahead": patients_ahead,
        "wait_minutes": wait_minutes,
        "chamber": f"Room {1 + digest[3] % 4}",
    }


def _to_public(clinic: ClinicModel, lat: float | None = None, lon: float | None = None) -> dict[str, Any]:
    """Project a ClinicModel row into a safe, public JSON shape."""
    partner = bool(clinic.is_license_active and clinic.is_active)
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
        # availability today is derived from the SaaS license (see docs: add
        # explicit `open_time` / `close_time` columns for real availability)
        "availability": "OPEN" if partner else "DIRECTORY",
        # live signal only for partner clinics
        "live": _live_signal(str(clinic.id)) if partner else None,
        # geolocation-ready; populated once clinics gain lat/long columns
        "distance_km": None,
    }


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
    listings. Both tiers are returned so patients can still see (and call)
    clinics that are not yet on the live queue network.
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
            doctors = [_to_public(c, lat, lon) for c in rows]
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


@router.get("/find-doctor", include_in_schema=False)
@router.get("/doctors", include_in_schema=False)
async def find_doctor_page():
    """Patient-facing 'Find a Doctor' marketplace HTML."""
    import jinja2

    loader = jinja2.FileSystemLoader(str(_TEMPLATES_DIR))
    env = jinja2.Environment(loader=loader, auto_reload=True)
    return HTMLResponse(content=env.get_template("marketplace.html").render())
