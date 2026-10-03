"""Clinic tools — one page where every capability is actually reachable.

Why this page exists
--------------------
Blocks 2-8 shipped as APIs, and every one of them was verified programmatically.
But a doctor cannot call an endpoint. Searching for "health card revoke" in the
UI found nothing, because there was nothing: the feature was real, tested, live,
and invisible. A capability nobody can reach is not a shipped feature — it is a
promise with tests.

So this page is the index of everything that has no natural home in the existing
screens, grouped by what a clinic is trying to DO rather than by which module
implemented it:

    Patient record   → health card, access log, revoke, FHIR export
    Referrals        → incoming, accept/decline, send one out
    Queue health     → EWT accuracy (are our wait times honest?)
    Reviews          → verified reviews and their effect on the rating
    Growth           → patients asking for clinics not on the network
    Ingestion        → what the crawler found, and what it rejected
    App              → is the PWA installable?

Every action on this page calls an endpoint that already existed and was already
tested. Nothing new is introduced here — it is a front door.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import jinja2
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Clinic Tools"])

_TEMPLATES_DIR = Path(__file__).parents[4] / "templates"


def _session(request: Request) -> dict:
    from src.presentation.opd.routes.opd_routes import _require_opd_session

    return _require_opd_session(request)


@router.get("/tools", include_in_schema=False)
async def tools_page(request: Request):
    """The clinic tools hub. Requires a doctor/reception session."""
    sess = _session(request)

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)), auto_reload=True
    )
    html = env.get_template("clinic_tools.html").render(
        staff_name=str(sess.get("name") or "Staff"),
        role=str(sess.get("role") or sess.get("doctor_id") or "doctor"),
    )
    return HTMLResponse(html)


@router.get("/opd/api/tools/doctor-queue-today", include_in_schema=False)
async def todays_queue(request: Request):
    """Today's patients, for the pick-lists on the tools page.

    A patient id has to be typed somewhere, and a free-text box guarantees
    typos. This gives the page real ids to choose from, so "revoke this
    patient's card" cannot silently target a mistyped id.
    """
    from src.shared.infrastructure.database import async_session_factory
    from src.presentation.queue_engine.routes.queue_engine_routes import (
        _active_entries,
        _resolve_clinic_id,
    )

    sess = _session(request)
    clinic_id = await _resolve_clinic_id(sess)
    doctor_id = str(sess.get("doctor_id") or "chief")

    async with async_session_factory() as session:
        entries = await _active_entries(session, clinic_id, doctor_id)

    seen: set[str] = set()
    patients: list[dict[str, Any]] = []
    for entry in entries:
        key = str(entry.patient_id or "")
        if not key or key in seen:
            continue
        seen.add(key)
        patients.append(
            {
                "patient_id": key,
                "patient_name": entry.patient_name or "",
                "token_number": entry.token_number,
                "status": (entry.status or "").upper(),
            }
        )

    return {"ok": True, "clinic_id": clinic_id, "count": len(patients), "patients": patients}


@router.get("/opd/api/tools/recent-patients", include_in_schema=False)
async def recent_patients(request: Request, limit: int = 25):
    """Recently seen patients (completed visits), for the tools pick-lists.

    Today's live queue is not enough for the access-log and FHIR actions — a
    patient asking "who opened my record?" or "give me my records" is usually
    asking about a visit that already finished.
    """
    import sqlalchemy as sa

    from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel
    from src.presentation.queue_engine.routes.queue_engine_routes import (
        _resolve_clinic_id,
    )
    from src.shared.infrastructure.database import async_session_factory

    sess = _session(request)
    clinic_id = await _resolve_clinic_id(sess)
    try:
        cap = max(1, min(100, int(limit)))
    except (TypeError, ValueError):
        cap = 25

    async with async_session_factory() as session:
        stmt = (
            sa.select(QueueEntryModel)
            .where(QueueEntryModel.service_code == "OPD")
            .order_by(QueueEntryModel.created_at.desc())
            .limit(cap * 3)
        )
        if clinic_id:
            stmt = stmt.where(QueueEntryModel.clinic_id == clinic_id)
        rows = list((await session.execute(stmt)).scalars().all())

    seen: set[str] = set()
    patients: list[dict[str, Any]] = []
    for entry in rows:
        key = str(entry.patient_id or "")
        if not key or key in seen:
            continue
        seen.add(key)
        patients.append(
            {
                "patient_id": key,
                "patient_name": entry.patient_name or "",
                "status": (entry.status or "").upper(),
                "token_number": entry.token_number,
                "visit_id": entry.visit_id or "",
            }
        )
        if len(patients) >= cap:
            break

    return {"ok": True, "clinic_id": clinic_id, "count": len(patients), "patients": patients}


@router.get("/opd/api/tools/summary", include_in_schema=False)
async def tools_summary(request: Request):
    """Counts for the tools hub, so each card can show whether it has anything.

    A hub of empty sections is indistinguishable from a hub of broken ones; the
    numbers make "nothing to do" visibly different from "nothing works".
    """
    import sqlalchemy as sa

    from src.infrastructure.clinic.models.clinic_model import ClinicModel
    from src.infrastructure.clinic.models.lead_model import ClinicLeadModel, STATUS_NEW
    from src.infrastructure.clinic.models.referral_model import (
        STATUS_PENDING,
        ReferralModel,
    )
    from src.infrastructure.clinic.models.review_model import ClinicReviewModel
    from src.presentation.queue_engine.routes.queue_engine_routes import (
        _resolve_clinic_id,
    )
    from src.shared.infrastructure.database import async_session_factory

    sess = _session(request)
    clinic_id = await _resolve_clinic_id(sess)
    out: dict[str, Any] = {"clinic_id": clinic_id}

    try:
        async with async_session_factory() as session:
            if clinic_id:
                pending = await session.execute(
                    sa.select(sa.func.count(ReferralModel.id)).where(
                        ReferralModel.to_clinic_id == clinic_id,
                        ReferralModel.status == STATUS_PENDING,
                    )
                )
                out["referrals_pending"] = int(pending.scalar() or 0)

                reviews = await session.execute(
                    sa.select(
                        sa.func.count(ClinicReviewModel.id),
                        sa.func.avg(ClinicReviewModel.rating),
                    ).where(
                        ClinicReviewModel.clinic_id == clinic_id,
                        ClinicReviewModel.is_visible.is_(True),
                    )
                )
                row = reviews.first()
                out["reviews_visible"] = int(row[0] or 0) if row else 0
                out["reviews_average"] = (
                    round(float(row[1]), 2) if row and row[1] is not None else None
                )
            leads_new = await session.execute(
                sa.select(sa.func.count(ClinicLeadModel.id)).where(
                    ClinicLeadModel.status == STATUS_NEW
                )
            )
            out["leads_new"] = int(leads_new.scalar() or 0)

            crawled = await session.execute(
                sa.select(sa.func.count(ClinicModel.id)).where(
                    ClinicModel.source == "crawl"
                )
            )
            out["crawled_listings"] = int(crawled.scalar() or 0)
    except Exception as exc:  # pragma: no cover - the hub must still render
        logger.warning("tools summary failed: %s", exc)
        out["error"] = f"{type(exc).__name__}"

    return {"ok": True, **out}
