"""Verified review routes (Part F · F-07).

Flow:

    patient finishes visit
        → opens their tracking link (already in their WhatsApp)
        → POST /api/v1/reviews {tracking_token, rating, comment}
        → the token proves the visit; a COMPLETED entry is required
        → clinics.rating is recomputed with the Bayesian formula

The token is the whole verification story. No signup, no "rate us" email, no
anonymous drive-by — a review exists only if a real visit does.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from src.domain.clinic import reviews as review_rules
from src.infrastructure.clinic.models.clinic_model import ClinicModel
from src.infrastructure.clinic.models.review_model import ClinicReviewModel
from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel
from src.shared.infrastructure.database import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Reviews"])


async def _visible_ratings(session, clinic_id: str) -> list[int]:
    """Every visible rating for a clinic — the input to the Bayesian score."""
    rows = await session.execute(
        sa.select(ClinicReviewModel.rating).where(
            ClinicReviewModel.clinic_id == clinic_id,
            ClinicReviewModel.is_visible.is_(True),
        )
    )
    return [int(r[0]) for r in rows.all() if r[0] is not None]


async def recalculate_clinic_rating(session, clinic_id: str) -> dict[str, Any]:
    """Recompute ``clinics.rating`` / ``rating_count`` from visible reviews.

    Denormalised onto the clinic row on purpose: ranking must never aggregate
    the whole review table per search. Recomputed on every write, so it cannot
    drift — and a hidden review stops counting immediately.
    """
    ratings = await _visible_ratings(session, clinic_id)
    breakdown = review_rules.rating_breakdown(ratings)

    try:
        clinic_uuid = uuid.UUID(str(clinic_id))
    except (ValueError, AttributeError, TypeError):
        return breakdown

    clinic = await session.get(ClinicModel, clinic_uuid)
    if clinic is not None:
        clinic.rating = breakdown["rating"]
        clinic.rating_count = breakdown["count"]
    return breakdown


@router.post("/api/v1/reviews")
async def submit_review(request: Request):
    """Submit a review from a visit's tracking link.

    Body: ``{tracking_token, rating, comment?}``. The token must decode to a
    patient who has a COMPLETED (or later) visit, and each visit can be
    reviewed once.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body or {}

    token = str(body.get("tracking_token") or "").strip()
    rating = review_rules.clamp_rating(body.get("rating"))
    comment = str(body.get("comment") or "").strip()[:2000]

    if not token:
        return JSONResponse(
            {"ok": False, "error": "Tracking link chahiye — review sirf asli visit se."},
            status_code=400,
        )
    if rating is None:
        return JSONResponse(
            {"ok": False, "error": "1 se 5 ke beech star chunein."}, status_code=400
        )

    from src.presentation.staff.routes.staff_routes import decode_tracking_token

    patient_id = decode_tracking_token(token)
    if not patient_id:
        return JSONResponse(
            {"ok": False, "error": "Link purana ya galat hai — clinic se naya link lein."},
            status_code=400,
        )

    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                sa.select(QueueEntryModel)
                .where(
                    QueueEntryModel.patient_id == patient_id,
                    QueueEntryModel.service_code == "OPD",
                )
                .order_by(QueueEntryModel.created_at.desc())
                .limit(10)
            )
        ).scalars().all()

        # Prefer the newest COMPLETED visit; if there is none, fall back to the
        # newest visit of any state so the patient gets the TRUE reason
        # ("visit abhi poori nahi hui") instead of a misleading "visit not
        # found" that would send them to the reception desk for nothing.
        latest = rows[0] if rows else None
        completed = next(
            (e for e in rows if review_rules.is_reviewable_status(e.status)), None
        )
        visit = completed or latest
        allowed, reason = review_rules.eligibility(visit, now=now)
        if not allowed:
            return JSONResponse({"ok": False, "error": reason}, status_code=400)

        visit_id = str(visit.visit_id or "")
        clinic_id = str(visit.clinic_id or "")

        # One review per visit — a second submission updates the first rather
        # than stacking a second star onto the same visit.
        existing = (
            await session.execute(
                sa.select(ClinicReviewModel)
                .where(ClinicReviewModel.visit_id == visit_id)
                .limit(1)
            )
        ).scalars().first()

        if existing is not None:
            existing.rating = rating
            existing.comment = comment
            existing.updated_at = now
            review = existing
        else:
            review = ClinicReviewModel(
                id=uuid.uuid4(),
                clinic_id=clinic_id,
                doctor_id=str(visit.doctor_id or "chief"),
                patient_id=patient_id,
                queue_entry_id=str(visit.id),
                visit_id=visit_id,
                service_code=str(visit.service_code or "OPD"),
                visit_status=str(visit.status or ""),
                rating=rating,
                comment=comment,
                is_visible=True,
                created_at=now,
                updated_at=now,
            )
            session.add(review)

        await session.flush()
        breakdown = await recalculate_clinic_rating(session, clinic_id)
        await session.commit()

        clinic_name = ""
        try:
            clinic = await session.get(ClinicModel, uuid.UUID(clinic_id))
            clinic_name = clinic.clinic_name if clinic else ""
        except Exception:  # pragma: no cover - name is cosmetic
            pass

    return {
        "ok": True,
        "verified": True,
        "rating": rating,
        "clinic_name": clinic_name,
        "clinic_rating": breakdown["rating"],
        "clinic_review_count": breakdown["count"],
        "message": (
            f"Shukriya! {rating}★ review darj ho gaya. "
            f"{clinic_name or 'Clinic'} ka ab score {breakdown['rating']} hai "
            f"({breakdown['count']} verified reviews)."
        ),
    }


@router.get("/api/v1/reviews")
async def list_reviews(
    clinic_id: str = Query(...),
    limit: int = Query(default=20),
):
    """Public, visible reviews for one clinic."""
    try:
        clinic_uuid = uuid.UUID(str(clinic_id).strip())
    except (ValueError, AttributeError, TypeError):
        return JSONResponse({"ok": False, "error": "Clinic nahi mila."}, status_code=404)

    try:
        cap = max(1, min(100, int(limit)))
    except (TypeError, ValueError):
        cap = 20

    async with async_session_factory() as session:
        clinic = await session.get(ClinicModel, clinic_uuid)
        if clinic is None:
            return JSONResponse({"ok": False, "error": "Clinic nahi mila."}, status_code=404)
        cid = str(clinic.id)

        rows = (
            await session.execute(
                sa.select(ClinicReviewModel)
                .where(
                    ClinicReviewModel.clinic_id == cid,
                    ClinicReviewModel.is_visible.is_(True),
                )
                .order_by(ClinicReviewModel.created_at.desc())
                .limit(cap)
            )
        ).scalars().all()
        ratings = await _visible_ratings(session, cid)
        clinic_name = clinic.clinic_name or ""

    breakdown = review_rules.rating_breakdown(ratings)
    return {
        "ok": True,
        "clinic_id": cid,
        "clinic_name": clinic_name,
        **breakdown,
        "reviews": [
            {
                "rating": int(r.rating),
                # No patient name: a review must not publish who visited a
                # clinic, which in a small town is itself health information.
                "comment": r.comment or "",
                "visit_type": r.service_code or "OPD",
                "verified": True,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ],
    }


@router.post("/api/v1/reviews/{review_id}/hide", include_in_schema=False)
async def hide_review(request: Request, review_id: str):
    """Staff moderation: hide a review and recompute the clinic's score.

    Nothing is deleted — hiding is reversible, and the row remains as an audit
    trail of what was published and when it was withdrawn.
    """
    from src.presentation.opd.routes.opd_routes import _require_opd_session

    _require_opd_session(request)

    try:
        body = await request.json()
    except Exception:
        body = {}
    reason = str((body or {}).get("reason") or "").strip()[:200]

    try:
        rid = uuid.UUID(str(review_id))
    except (ValueError, AttributeError, TypeError):
        return JSONResponse({"ok": False, "error": "Review nahi mila."}, status_code=404)

    async with async_session_factory() as session:
        review = await session.get(ClinicReviewModel, rid)
        if review is None:
            return JSONResponse({"ok": False, "error": "Review nahi mila."}, status_code=404)
        review.is_visible = False
        review.hidden_reason = reason or "staff hidden"
        review.updated_at = datetime.now(timezone.utc)
        await session.flush()
        breakdown = await recalculate_clinic_rating(session, str(review.clinic_id))
        await session.commit()

    return {
        "ok": True,
        "clinic_rating": breakdown["rating"],
        "clinic_review_count": breakdown["count"],
        "message": (
            f"Review hide ho gaya. Clinic ka naya score {breakdown['rating']} "
            f"({breakdown['count']} reviews)."
        ),
    }
