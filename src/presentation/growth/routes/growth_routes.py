"""Growth routes — invite pipeline + city landing pages (BLOCK 4 · GRW-02/03).

GRW-02 · the invite that used to be a toast
------------------------------------------
Every non-partner clinic in the marketplace carried a "📢 Invite to GHOS Live
Queue" button that only displayed a thank-you message. That threw away the most
valuable sales signal the product creates: a real patient, in a real city,
asking for a clinic that is not on the network yet. Now it is recorded, counted
per clinic, and surfaced as an outreach pipeline.

GRW-03 · city pages
-------------------
``/doctors/<city>`` is a server-rendered, indexable landing page for one city.
It exists because "cardiologist in Jodhpur" is what a patient actually types
into Google, and until now the marketplace could only be reached by people who
already knew the product. The page is real content from real data — not an SEO
stub, which would eventually be penalised and, worse, would waste a patient's
click.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import jinja2
import sqlalchemy as sa
from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from src.domain.clinic import opening_hours
from src.infrastructure.clinic.models.clinic_model import ClinicModel
from src.infrastructure.clinic.models.lead_model import (
    PIPELINE_ORDER,
    SOURCE_ADMIN,
    SOURCE_PATIENT_INVITE,
    STATUS_CONTACTED,
    STATUS_DECLINED,
    STATUS_INTERESTED,
    STATUS_LABEL,
    STATUS_NEW,
    STATUS_ONBOARDED,
    ClinicLeadModel,
)
from src.shared.infrastructure.database import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Growth"])

from pathlib import Path

_TEMPLATES_DIR = Path(__file__).parents[4] / "templates"

#: Cap the demand notes kept per lead, so one noisy clinic cannot bloat a row.
MAX_DEMAND_NOTES = 12


# ── GRW-02 · invite a clinic ────────────────────────────────────────────────


def _merge_demand(existing: str, addition: str) -> str:
    """Append a demand note, de-duplicated and capped.

    Keeps the note list quotable in a sales call: "patients ne 7 baar poocha,
    inme se 4 ne 'seene me dard' likha" is a far stronger pitch than a count.
    """
    note = (addition or "").strip()[:120]
    items = [x.strip() for x in (existing or "").split("|") if x.strip()]
    if note and note.lower() not in {i.lower() for i in items}:
        items.append(note)
    return "|".join(items[-MAX_DEMAND_NOTES:])


@router.post("/api/v1/marketplace/invite")
async def marketplace_invite(request: Request):
    """A patient asks for a clinic to join the live-queue network.

    Body: ``{clinic_id?, clinic_name?, city?, specialty?, problem?}``.

    Idempotent per clinic: asking twice increments the demand count rather than
    creating a duplicate lead, because "how many patients wanted this" is the
    number that decides whether outreach is worth doing.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body or {}

    clinic_id = str(body.get("clinic_id") or "").strip()
    clinic_name = str(body.get("clinic_name") or "").strip()[:200]
    city = str(body.get("city") or "").strip()[:100]
    specialty = str(body.get("specialty") or "").strip()[:100]
    problem = str(body.get("problem") or "").strip()[:120]

    if not clinic_id and not clinic_name:
        return JSONResponse(
            {"ok": False, "error": "Kis clinic ke liye request hai — wo chunein."},
            status_code=400,
        )

    now = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        lead: ClinicLeadModel | None = None

        if clinic_id:
            clinic_uuid = _parse_uuid(clinic_id)
            if clinic_uuid is not None:
                row = await session.execute(
                    sa.select(ClinicLeadModel)
                    .where(ClinicLeadModel.clinic_id == str(clinic_uuid))
                    .limit(1)
                )
                lead = row.scalars().first()
                if lead is None:
                    clinic = await session.get(ClinicModel, clinic_uuid)
                    if clinic is not None:
                        clinic_name = clinic_name or (clinic.clinic_name or "")
                        city = city or (clinic.city or "")
                        specialty = specialty or (clinic.specialty or "")

        if lead is None and clinic_name:
            row = await session.execute(
                sa.select(ClinicLeadModel)
                .where(
                    sa.func.lower(ClinicLeadModel.clinic_name) == clinic_name.lower(),
                    sa.func.lower(ClinicLeadModel.city) == city.lower(),
                )
                .limit(1)
            )
            lead = row.scalars().first()

        if lead is None:
            lead = ClinicLeadModel(
                id=uuid.uuid4(),
                clinic_id=clinic_id or None,
                clinic_name=clinic_name,
                city=city,
                state=str(body.get("state") or "").strip()[:100],
                specialty=specialty,
                phone=str(body.get("phone") or "").strip()[:20],
                request_count=1,
                demand_notes=_merge_demand("", problem),
                source=SOURCE_PATIENT_INVITE,
                status=STATUS_NEW,
                created_at=now,
                updated_at=now,
                updated_by="marketplace",
            )
            session.add(lead)
        else:
            lead.request_count = int(lead.request_count or 0) + 1
            lead.demand_notes = _merge_demand(lead.demand_notes, problem)
            lead.updated_at = now
            # A fresh ask is a good reason to resurface a lead that had gone
            # quiet — demand changed, so the outreach decision may have too.
            if lead.status == STATUS_DECLINED and lead.request_count >= 3:
                lead.status = STATUS_CONTACTED
            # Only keep the name a patient typed if we have nothing better.
            lead.clinic_name = lead.clinic_name or clinic_name
            lead.city = lead.city or city
            lead.specialty = lead.specialty or specialty

        await session.commit()
        count = int(lead.request_count or 1)
        name = lead.clinic_name or "Clinic"

    return {
        "ok": True,
        "clinic_name": name,
        "request_count": count,
        "message": (
            f"Shukriya! {name} ke liye aapki request darj ho gayi "
            f"({count} patient{'s' if count != 1 else ''} ne poocha hai). "
            "Hum unse baat karenge — join karte hi aapko yahan dikhega."
        ),
    }


@router.get("/opd/api/leads", include_in_schema=False)
async def list_leads(
    request: Request,
    status: str = Query(default=""),
    limit: int = Query(default=50),
):
    """The outreach pipeline, highest demand first.

    Sorted by demand rather than by date on purpose: a clinic 40 patients asked
    for is a better use of a phone call than one asked for this morning.
    """
    from src.presentation.opd.routes.opd_routes import _require_opd_session

    _require_opd_session(request)

    wanted = (status or "").strip().upper()
    if wanted and wanted not in PIPELINE_ORDER:
        wanted = ""
    try:
        cap = max(1, min(200, int(limit)))
    except (TypeError, ValueError):
        cap = 50

    async with async_session_factory() as session:
        stmt = sa.select(ClinicLeadModel)
        if wanted:
            stmt = stmt.where(ClinicLeadModel.status == wanted)
        stmt = stmt.order_by(
            ClinicLeadModel.request_count.desc(), ClinicLeadModel.created_at.desc()
        ).limit(cap)
        rows = list((await session.execute(stmt)).scalars().all())

        all_rows = list((await session.execute(sa.select(ClinicLeadModel))).scalars().all())

    by_status: dict[str, int] = {stage: 0 for stage in PIPELINE_ORDER}
    for row in all_rows:
        by_status[row.status] = by_status.get(row.status, 0) + 1

    return {
        "ok": True,
        "total": len(all_rows),
        "by_status": by_status,
        "by_status_label": {k: STATUS_LABEL.get(k, k) for k in by_status},
        "returned": len(rows),
        "leads": [
            {
                "id": str(r.id),
                "clinic_id": r.clinic_id or "",
                "clinic_name": r.clinic_name,
                "city": r.city,
                "specialty": r.specialty,
                "phone": r.phone,
                "request_count": int(r.request_count or 0),
                "demand_notes": [n for n in (r.demand_notes or "").split("|") if n],
                "status": r.status,
                "status_label": STATUS_LABEL.get(r.status, r.status),
                "source": r.source,
                "note": r.note,
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "last_contacted_at": (
                    r.last_contacted_at.isoformat() if r.last_contacted_at else ""
                ),
            }
            for r in rows
        ],
    }


@router.post("/opd/api/leads/{lead_id}", include_in_schema=False)
async def update_lead(request: Request, lead_id: str):
    """Move a lead along the pipeline. Body: ``{status?, note?}``."""
    from src.presentation.opd.routes.opd_routes import _require_opd_session

    sess = _require_opd_session(request)

    lead_uuid = _parse_uuid(lead_id)
    if lead_uuid is None:
        return JSONResponse({"ok": False, "error": "Lead nahi mila."}, status_code=404)

    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body or {}
    new_status = str(body.get("status") or "").strip().upper()
    note = str(body.get("note") or "").strip()[:2000]

    if new_status and new_status not in PIPELINE_ORDER:
        return JSONResponse(
            {"ok": False, "error": f"Status '{new_status}' samajh nahi aaya."},
            status_code=400,
        )

    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        lead = await session.get(ClinicLeadModel, lead_uuid)
        if lead is None:
            return JSONResponse({"ok": False, "error": "Lead nahi mila."}, status_code=404)
        if new_status:
            lead.status = new_status
            lead.last_contacted_at = now
        if note:
            lead.note = note
        lead.updated_by = str(sess.get("name") or "staff")
        lead.updated_at = now
        await session.commit()
        status = lead.status
        name = lead.clinic_name or "Clinic"
        count = int(lead.request_count or 0)

    return {
        "ok": True,
        "status": status,
        "status_label": STATUS_LABEL.get(status, status),
        "message": f"{name} → {STATUS_LABEL.get(status, status)} ({count} patient requests).",
    }


def _parse_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


# ── GRW-03 · city landing pages ─────────────────────────────────────────────


async def _city_data(city: str, limit: int = 60) -> dict[str, Any]:
    """Real clinics for one city, with their real availability and live queue.

    Reuses the marketplace projection so a city page can never show a clinic as
    open while the search page shows it closed — there is one source of truth.
    """
    from src.presentation.marketplace.routes.marketplace_routes import _decorate, _to_public

    async with async_session_factory() as session:
        stmt = (
            sa.select(ClinicModel)
            .where(
                ClinicModel.is_active == True,  # noqa: E712
                sa.func.lower(ClinicModel.city) == city.strip().lower(),
            )
            .order_by(ClinicModel.is_license_active.desc(), ClinicModel.doctor_name.asc())
            .limit(limit)
        )
        rows = list((await session.execute(stmt)).scalars().all())

        from src.presentation.marketplace.routes.marketplace_routes import _queue_map

        queue = await _queue_map([str(c.id) for c in rows])

    doctors = [_decorate(_to_public(c, queue.get(str(c.id)))) for c in rows]
    doctors.sort(key=lambda d: (d.get("tier", 2), -(d.get("rank_score") or 0)))
    return {
        "doctors": doctors,
        "total": len(doctors),
        "partners": sum(1 for d in doctors if d["tier"] == 1),
    }


@router.get("/doctors/{city}", include_in_schema=False)
async def doctors_in_city(city: str):
    """Indexable city landing page — "cardiologist in Jodhpur", answered.

    Server-rendered on purpose: a crawler gets the full list in the first
    response, and a patient on a slow connection sees content without waiting
    for the search API.
    """
    clean = (city or "").strip().replace("-", " ")
    if not clean or len(clean) > 60:
        return HTMLResponse(_city_error("City ka naam samajh nahi aaya."), status_code=404)

    data = await _city_data(clean)
    if not data["total"]:
        return HTMLResponse(
            _city_error(
                f"{clean.title()} me abhi koi clinic listed nahi hai.",
                city=clean,
            ),
            status_code=404,
        )

    # Specialties present in this city — real ones, so each link lands on
    # results rather than an empty page.
    specialties: dict[str, int] = {}
    for doctor in data["doctors"]:
        key = doctor.get("specialty") or ""
        if key:
            specialties[key] = specialties.get(key, 0) + 1
    specialty_list = sorted(specialties.items(), key=lambda kv: (-kv[1], kv[0]))

    open_now = [d for d in data["doctors"] if d.get("is_open_now")]
    zero_wait = [
        d for d in data["doctors"]
        if (d.get("live") or {}).get("patients_ahead") == 0 and d.get("partner")
    ]

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)), auto_reload=True
    )
    html = env.get_template("city_doctors.html").render(
        city=clean.title(),
        city_slug=clean.strip().lower().replace(" ", "-"),
        city_lower=clean.lower(),
        doctors=data["doctors"],
        total=data["total"],
        partners=data["partners"],
        open_now_count=len(open_now),
        zero_wait_count=len(zero_wait),
        specialties=specialty_list,
    )
    return HTMLResponse(content=html)


def _city_error(message: str, city: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>Doctors — GIL Clinic</title>
<style>
 body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        background:#f1f5f9;display:flex;align-items:center;justify-content:center;
        min-height:100vh;margin:0;padding:20px; }}
 .box {{ background:#fff;border-radius:16px;padding:34px;text-align:center;max-width:440px;
         box-shadow:0 12px 40px rgba(15,23,42,.1); }}
 h1 {{ font-size:19px;color:#0f172a;margin-bottom:10px; }}
 p {{ color:#64748b;font-size:14px;line-height:1.7; }}
 a {{ display:inline-block;margin-top:14px;padding:11px 18px;border-radius:11px;
      background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;
      font-weight:700;text-decoration:none;font-size:14px; }}
</style></head><body>
<div class="box"><div style="font-size:40px;margin-bottom:8px;">🏥</div>
<h1>{message}</h1>
<p>GIL CLINIC network me har sheher ke doctors dheere-dheere jud rahe hain.</p>
<a href="/find-doctor">Poora doctor directory dekhein</a></div>
</body></html>"""
