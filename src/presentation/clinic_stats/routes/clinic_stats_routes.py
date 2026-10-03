"""Clinic stats — EWT accuracy and the network overview (Part F · F-03 / F-08).

Why this module exists
---------------------
The EWT engine calls itself "self-calibrating". Without a measurement that is a
claim, not a fact. F-03 compares the wait we PROMISED (``estimated_minutes``,
stamped at booking) against the wait we DELIVERED (booking → called), so the
±5-minute North Star in the blueprint is something the product can prove or
fail.

``/api/v1/admin/network`` (F-08) is the same idea one level up: a live,
**PHI-free** view of every clinic in the network. It deliberately exposes a
token count and a last-active timestamp and nothing else — no patient names, no
phone numbers, no clinical data. A super-admin needs to know whether the
network is alive; that question never requires reading a chart.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from src.domain.queue import ewt
from src.infrastructure.clinic.models.clinic_model import ClinicModel
from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel
from src.shared.infrastructure.database import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Clinic Stats"])

#: How far back the accuracy report looks by default.
DEFAULT_ACCURACY_DAYS = 30
#: Cap the rows read, so a busy clinic cannot blow the 100 CPU-second budget.
MAX_ACCURACY_ROWS = 3000


def _clinic_id_of(sess: dict) -> str:
    for key in ("clinic_id", "clinicId"):
        value = str(sess.get(key) or "").strip()
        if value:
            return value
    lic = sess.get("lic_info") or {}
    if isinstance(lic, dict):
        return str(lic.get("clinic_id") or "").strip()
    return ""


def _age_minutes(value: Any) -> int | None:
    """Minutes since a timestamp, tolerant of naive values.

    SQLite hands back naive datetimes even for a ``DateTime(timezone=True)``
    column, while PostgreSQL returns aware ones. Comparing the two raises
    ``TypeError: can't subtract offset-naive and offset-aware datetimes`` — so
    normalise once, here, rather than letting a display field 500 a page.
    """
    if value is None:
        return None
    moment = value if getattr(value, "tzinfo", None) else value.replace(tzinfo=timezone.utc)
    try:
        return int((datetime.now(timezone.utc) - moment).total_seconds() // 60)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


# ── F-03 · EWT accuracy for one clinic ──────────────────────────────────────


@router.get("/opd/api/stats/ewt-accuracy", include_in_schema=False)
async def ewt_accuracy(
    request: Request,
    days: int = Query(default=DEFAULT_ACCURACY_DAYS),
    tolerance: int = Query(default=ewt.ACCURACY_TOLERANCE_MINUTES),
):
    """Promised vs delivered wait, for the logged-in doctor's clinic.

    Only counts entries that have BOTH a promise and a real call time, and
    reports how many were skipped — an accuracy figure over a silently filtered
    subset would be worse than no figure at all.
    """
    from src.presentation.opd.routes.opd_routes import _require_opd_session

    sess = _require_opd_session(request)
    clinic_id = _clinic_id_of(sess)
    if not clinic_id:
        from src.presentation.queue_engine.routes.queue_engine_routes import (
            _resolve_clinic_id,
        )

        clinic_id = await _resolve_clinic_id(sess)

    try:
        window = max(1, min(365, int(days)))
    except (TypeError, ValueError):
        window = DEFAULT_ACCURACY_DAYS
    try:
        limit = max(1, min(60, int(tolerance)))
    except (TypeError, ValueError):
        limit = ewt.ACCURACY_TOLERANCE_MINUTES

    since = datetime.now(timezone.utc) - timedelta(days=window)
    rows: list[Any] = []
    try:
        async with async_session_factory() as session:
            stmt = (
                sa.select(
                    QueueEntryModel.estimated_minutes,
                    QueueEntryModel.created_at,
                    QueueEntryModel.called_at,
                    QueueEntryModel.started_at,
                )
                .where(
                    QueueEntryModel.service_code == "OPD",
                    QueueEntryModel.created_at >= since,
                    QueueEntryModel.estimated_minutes.is_not(None),
                )
                .order_by(QueueEntryModel.created_at.desc())
                .limit(MAX_ACCURACY_ROWS)
            )
            if clinic_id:
                stmt = stmt.where(QueueEntryModel.clinic_id == clinic_id)
            result = await session.execute(stmt)
            rows = [
                {
                    "estimated_minutes": r[0],
                    "created_at": r[1],
                    "called_at": r[2],
                    "started_at": r[3],
                }
                for r in result.all()
            ]
    except Exception as exc:  # pragma: no cover - report must never break a page
        logger.warning("ewt accuracy query failed: %s", exc)
        return {"ok": False, "error": "Report abhi nahi ban saki."}

    report = ewt.accuracy_report(rows, tolerance=limit)
    return {
        "ok": True,
        "clinic_id": clinic_id,
        "days": window,
        "north_star": f"±{ewt.ACCURACY_TOLERANCE_MINUTES} min",
        **report,
    }


# ── F-08 · Network overview (PHI-free) ──────────────────────────────────────


@router.get("/api/v1/admin/network", include_in_schema=False)
async def admin_network(
    request: Request,
    token: str = Query(default=""),
):
    """Live, PHI-free overview of every clinic in the network.

    Deliberately returns **no patient-identifying data**: per clinic only a
    count of tokens, the last activity timestamp, licence state, and whether
    the chamber is open. A network dashboard never needs a patient's name, and
    returning one would turn an operations page into a privacy incident.

    Auth: super-admin session, or the seed token for a quick health look.
    """
    from src.presentation.marketplace.routes.marketplace_routes import SEED_TOKEN

    authorized = False
    if token and token == SEED_TOKEN:
        authorized = True
    if not authorized:
        try:
            from src.presentation.admin.routes.auth_routes import (
                require_admin_session,
            )

            require_admin_session(request)
            authorized = True
        except Exception:
            authorized = False
    if not authorized:
        return JSONResponse(
            {"ok": False, "error": "Admin login chahiye."}, status_code=401
        )

    today = datetime.now(timezone.utc).date()
    since = datetime.now(timezone.utc) - timedelta(days=7)

    try:
        from src.infrastructure.queue.models.chamber_session_model import (
            ChamberSessionModel,
        )

        async with async_session_factory() as session:
            clinics = list(
                (await session.execute(sa.select(ClinicModel))).scalars().all()
            )

            # Per clinic: active token count, total tokens, last activity.
            stats_rows = (
                await session.execute(
                    sa.select(
                        QueueEntryModel.clinic_id,
                        sa.func.count(QueueEntryModel.id),
                        sa.func.max(QueueEntryModel.created_at),
                    )
                    .where(
                        QueueEntryModel.service_code == "OPD",
                        QueueEntryModel.created_at >= since,
                    )
                    .group_by(QueueEntryModel.clinic_id)
                )
            ).all()
            stats = {
                str(r[0]): {"tokens_7d": int(r[1] or 0), "last_active": r[2]}
                for r in stats_rows
                if r[0]
            }

            live_rows = (
                await session.execute(
                    sa.select(QueueEntryModel.clinic_id)
                    .where(
                        QueueEntryModel.completed_at.is_(None),
                        QueueEntryModel.delivered_at.is_(None),
                        QueueEntryModel.status.in_(
                            ("WAITING", "CALLED", "HOLD", "IN_PROGRESS")
                        ),
                    )
                )
            ).all()
            live_counts: dict[str, int] = {}
            for row in live_rows:
                if row[0]:
                    key = str(row[0])
                    live_counts[key] = live_counts.get(key, 0) + 1

            # ``is_open`` is a Python property on the model (opened_at is set,
            # closed_at is not), so it cannot be selected — read the two
            # timestamps and apply the same rule here.
            chamber_rows = (
                await session.execute(
                    sa.select(
                        ChamberSessionModel.clinic_id,
                        ChamberSessionModel.opened_at,
                        ChamberSessionModel.closed_at,
                    ).where(ChamberSessionModel.session_date == today)
                )
            ).all()
            chamber: dict[str, bool] = {}
            for cid, opened_at, closed_at in chamber_rows:
                if cid:
                    key = str(cid)
                    is_open = opened_at is not None and closed_at is None
                    chamber[key] = bool(chamber.get(key)) or is_open
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("admin network query failed: %s", exc)
        return JSONResponse(
            {"ok": False, "error": f"Network view abhi available nahi ({type(exc).__name__})."},
            status_code=500,
        )

    nodes = []
    for clinic in clinics:
        cid = str(clinic.id)
        stat = stats.get(cid, {})
        last = stat.get("last_active")
        nodes.append(
            {
                # Identity of the CLINIC only — never a patient.
                "clinic_id": cid,
                "clinic_code": clinic.clinic_code or "",
                "clinic_name": clinic.clinic_name or "",
                "doctor_name": clinic.doctor_name or "",
                "city": (clinic.city or "").strip(),
                "specialty": (clinic.specialty or "").strip(),
                "partner": bool(clinic.is_license_active and clinic.is_active),
                "is_license_active": bool(clinic.is_license_active),
                "tokens_7d": int(stat.get("tokens_7d") or 0),
                "live_tokens": int(live_counts.get(cid, 0)),
                "chamber_open": chamber.get(cid),
                "last_active": last.isoformat() if last else "",
                "last_active_ago_minutes": _age_minutes(last),
            }
        )

    nodes.sort(key=lambda n: (-int(n["tokens_7d"]), n["clinic_name"].lower()))
    active_today = [n for n in nodes if n["live_tokens"] > 0]
    return {
        "ok": True,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "phi_free": True,
        "note": (
            "Sirf clinic-level numbers — koi patient ka naam, phone ya clinical "
            "data is page par nahi aata."
        ),
        "totals": {
            "clinics": len(nodes),
            "partners": sum(1 for n in nodes if n["partner"]),
            "clinics_with_live_tokens": len(active_today),
            "live_tokens": sum(n["live_tokens"] for n in nodes),
            "tokens_7d": sum(n["tokens_7d"] for n in nodes),
            "chambers_open": sum(1 for n in nodes if n["chamber_open"]),
        },
        "nodes": nodes,
    }
