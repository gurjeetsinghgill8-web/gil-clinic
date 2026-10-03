"""Queue Engine routes — chamber gate, token hold/return, live EWT feed.

Why a separate module (and why ``opd_routes.py`` is not touched)
---------------------------------------------------------------
``opd_routes.py`` is 4000+ lines and is the busiest file in the product, so the
new queue behaviour lives here and borrows its session guard lazily — the same
pattern ``health_card_routes.py`` already uses. Guardrail #2 in the master
blueprint.

What this module adds (master blueprint v1.1, Part B + Part D):

  * **E-01 Chamber gate** — ``▶ START OPD``. The EWT countdown must not run
    until the doctor is actually inside the chamber, otherwise the app promises
    "18 min" at 9:00 while the doctor is still stuck in traffic.
  * **E-02 Token hold & return** — a patient called while in the washroom goes
    to HOLD, and on return is re-inserted directly after whoever is inside the
    chamber (Next + 1) instead of being punished to the back of the line.
  * **B4 Live EWT feed** — per-patient wait for the doctor's screen, plus the
    🟡 / 🔴 delay badge.
  * **E-03b Leave-now link** — a ``wa.me`` deep link the receptionist can tap.
    No server cron and no paid WhatsApp gateway: PA free has neither.

All endpoints are additive. Nothing here deletes data or changes existing
behaviour for a clinic that does not use it.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.domain.queue import ewt, travel
from src.infrastructure.queue.models.chamber_session_model import ChamberSessionModel
from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel
from src.shared.infrastructure.database import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/opd/api", tags=["Queue Engine"])

#: Statuses that mean "this patient is still part of today's live queue".
ACTIVE_STATUSES = ("WAITING", "CALLED", "HOLD", "IN_PROGRESS")
#: Statuses that may be parked on hold.
HOLDABLE_STATUSES = ("WAITING", "CALLED")
#: One free re-queue per patient; a second one goes to the back (abuse guard).
MAX_FREE_REQUEUES = 1


# ── session / scope helpers ─────────────────────────────────────────────────


def _sess(request: Request) -> dict:
    from src.presentation.opd.routes.opd_routes import _require_opd_session  # lazy

    return _require_opd_session(request)


async def _resolve_clinic_id(sess: dict) -> str:
    """Best-effort clinic id for the logged-in doctor.

    Resolution order: session → licence info → OPD settings → the clinic of the
    most recent OPD queue entry today. A single-clinic deployment therefore
    always resolves, and a multi-tenant one uses the doctor's own clinic.
    """
    for key in ("clinic_id", "clinicId"):
        value = str(sess.get(key) or "").strip()
        if value:
            return value

    lic = sess.get("lic_info") or {}
    if isinstance(lic, dict):
        value = str(lic.get("clinic_id") or "").strip()
        if value:
            return value

    doctor_id = str(sess.get("doctor_id") or "").strip()
    if doctor_id:
        try:
            from src.presentation.opd.routes.opd_routes import _get_settings  # lazy

            settings = await _get_settings(doctor_id, masked=True)
            value = str((settings or {}).get("clinic_id") or "").strip()
            if value:
                return value
        except Exception as exc:  # pragma: no cover - settings are best-effort
            logger.debug("chamber clinic resolve via settings failed: %s", exc)

    try:
        async with async_session_factory() as session:
            row = await session.execute(
                sa.select(QueueEntryModel.clinic_id)
                .where(
                    QueueEntryModel.service_code == "OPD",
                    QueueEntryModel.clinic_id.is_not(None),
                )
                .order_by(QueueEntryModel.created_at.desc())
                .limit(1)
            )
            return str(row.scalar() or "")
    except Exception:  # pragma: no cover - never block the request
        return ""


def _doctor_id(sess: dict) -> str:
    return str(sess.get("doctor_id") or "chief")


def _entry_key(entry: QueueEntryModel) -> float:
    """Stable ordering key: explicit sort_key, else the token number."""
    if entry.sort_key is not None:
        return float(entry.sort_key)
    return float(entry.token_number or 0)


def _today():
    return datetime.now(timezone.utc).date()


# ── shared query helpers ────────────────────────────────────────────────────


async def _active_entries(session, clinic_id: str, doctor_id: str) -> list[QueueEntryModel]:
    """Today's live OPD entries for one clinic + doctor, in dispatch order."""
    stmt = (
        sa.select(QueueEntryModel)
        .where(
            QueueEntryModel.service_code == "OPD",
            QueueEntryModel.completed_at.is_(None),
            QueueEntryModel.delivered_at.is_(None),
            QueueEntryModel.status.in_(ACTIVE_STATUSES),
        )
        .order_by(QueueEntryModel.sort_key.asc().nulls_last(), QueueEntryModel.token_number.asc())
    )
    if clinic_id:
        stmt = stmt.where(QueueEntryModel.clinic_id == clinic_id)
    if doctor_id:
        stmt = stmt.where(QueueEntryModel.doctor_id == doctor_id)
    return list((await session.execute(stmt)).scalars().all())


async def _history(session, clinic_id: str, doctor_id: str) -> list[Any]:
    """Last 30 days of completed consultations — the EWT learning sample."""
    from datetime import timedelta

    stmt = sa.select(
        QueueEntryModel.started_at, QueueEntryModel.completed_at
    ).where(
        QueueEntryModel.service_code == "OPD",
        QueueEntryModel.completed_at.is_not(None),
        QueueEntryModel.completed_at >= datetime.now(timezone.utc) - timedelta(days=30),
    )
    if clinic_id:
        stmt = stmt.where(QueueEntryModel.clinic_id == clinic_id)
    if doctor_id:
        stmt = stmt.where(QueueEntryModel.doctor_id == doctor_id)
    rows = (await session.execute(stmt.limit(500))).all()
    return [{"started_at": s, "completed_at": c} for s, c in rows]


async def _chamber(session, clinic_id: str, doctor_id: str) -> ChamberSessionModel | None:
    row = await session.execute(
        sa.select(ChamberSessionModel)
        .where(
            ChamberSessionModel.clinic_id == clinic_id,
            ChamberSessionModel.doctor_id == doctor_id,
            ChamberSessionModel.session_date == _today(),
        )
        .limit(1)
    )
    return row.scalars().first()


def _chamber_state(row: ChamberSessionModel | None) -> dict[str, Any]:
    """Chamber status plus the honest "we don't know yet" case."""
    if row is None:
        # No session recorded today: stay backward compatible (treat as open)
        # so untouched clinics keep showing live numbers.
        return {
            "chamber_open": True,
            "tracked": False,
            "scheduled_time": "",
            "opened_at": "",
            "closed_at": "",
            "late_minutes": 0,
        }
    return {
        "chamber_open": row.is_open,
        "tracked": True,
        "scheduled_time": row.scheduled_time or "",
        "opened_at": row.opened_at.isoformat() if row.opened_at else "",
        "closed_at": row.closed_at.isoformat() if row.closed_at else "",
        "late_minutes": row.late_arrival_minutes,
    }


# ── E-01 · Chamber gate ─────────────────────────────────────────────────────


@router.get("/chamber/status", include_in_schema=False)
async def chamber_status(request: Request):
    """Is the chamber open? Used by the dashboard and the marketplace."""
    sess = _sess(request)
    clinic_id = await _resolve_clinic_id(sess)
    doctor_id = _doctor_id(sess)
    async with async_session_factory() as session:
        row = await _chamber(session, clinic_id, doctor_id)
        state = _chamber_state(row)
        entries = await _active_entries(session, clinic_id, doctor_id)

    waiting = [e for e in entries if (e.status or "").upper() == "WAITING"]
    inside = [e for e in entries if (e.status or "").upper() == "IN_PROGRESS"]
    held = [e for e in entries if (e.status or "").upper() == "HOLD"]
    return {
        "ok": True,
        "clinic_id": clinic_id,
        "doctor_id": doctor_id,
        **state,
        "waiting": len(waiting),
        "in_progress": len(inside),
        "on_hold": len(held),
        "next_token": waiting[0].token_number if waiting else 0,
    }


@router.post("/chamber/open", include_in_schema=False)
async def chamber_open(request: Request):
    """▶ START OPD — the moment the EWT countdown is allowed to begin.

    Body (optional): ``{scheduled_time: "09:00", note: "..."}``.
    Idempotent: pressing it twice does not reset the arrival time.
    """
    sess = _sess(request)
    clinic_id = await _resolve_clinic_id(sess)
    doctor_id = _doctor_id(sess)
    try:
        body = await request.json()
    except Exception:
        body = {}
    scheduled = str((body or {}).get("scheduled_time") or "").strip()[:5]
    note = str((body or {}).get("note") or "").strip()[:200]
    now = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        row = await _chamber(session, clinic_id, doctor_id)
        if row is None:
            row = ChamberSessionModel(
                clinic_id=clinic_id,
                doctor_id=doctor_id,
                session_date=_today(),
                scheduled_time=scheduled,
                opened_at=now,
                opened_by=str(sess.get("name") or ""),
                note=note,
            )
            session.add(row)
        else:
            if row.opened_at is None:
                row.opened_at = now
                row.opened_by = str(sess.get("name") or "")
            # A doctor reopening after END OPD continues the same session.
            row.closed_at = None
            if scheduled and not row.scheduled_time:
                row.scheduled_time = scheduled
            if note:
                row.note = note
        await session.commit()
        await session.refresh(row)
        state = _chamber_state(row)
        entries = await _active_entries(session, clinic_id, doctor_id)

    waiting = [e for e in entries if (e.status or "").upper() in ("WAITING", "CALLED")]
    phones = await _phones_for(waiting)
    return {
        "ok": True,
        **state,
        "waiting": len(waiting),
        "message": (
            f"OPD shuru — {len(waiting)} patient line me hain. "
            "Ab wait time count hoga."
        ),
        "arrival_alert_urls": _arrival_links(sess, waiting, phones),
    }


@router.post("/chamber/close", include_in_schema=False)
async def chamber_close(request: Request):
    """⏹ END OPD — stops the live countdown for today."""
    sess = _sess(request)
    clinic_id = await _resolve_clinic_id(sess)
    doctor_id = _doctor_id(sess)
    async with async_session_factory() as session:
        row = await _chamber(session, clinic_id, doctor_id)
        if row is None:
            return JSONResponse({"ok": False, "error": "Aaj ka OPD session nahi mila."}, status_code=404)
        row.closed_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(row)
        state = _chamber_state(row)

    return {"ok": True, **state, "message": "OPD band — wait count ruk gaya."}


@router.post("/chamber/arrival-alert", include_in_schema=False)
async def chamber_arrival_alert(request: Request):
    """One tap after ▶ START OPD: WhatsApp links for everyone waiting.

    No cron, no paid gateway — the receptionist taps the link. (E-03b)
    """
    sess = _sess(request)
    clinic_id = await _resolve_clinic_id(sess)
    doctor_id = _doctor_id(sess)
    async with async_session_factory() as session:
        entries = await _active_entries(session, clinic_id, doctor_id)
    waiting = [e for e in entries if (e.status or "").upper() in ("WAITING", "CALLED")]
    links = _arrival_links(sess, waiting, await _phones_for(waiting))
    return {
        "ok": True,
        "count": len(links),
        "links": links,
        "message": f"{len(links)} patient ko bhejne ke links ready hain.",
    }


def _arrival_links(
    sess: dict,
    waiting: list[QueueEntryModel],
    phones: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """wa.me deep links (no API key, no cost) for the waiting patients."""
    doctor = str(sess.get("name") or "Doctor")
    out: list[dict[str, Any]] = []
    for entry in waiting[:15]:
        phone = _phone_of(entry, phones)
        if not phone:
            continue
        msg = (
            f"🔔 GIL CLINIC\n\n"
            f"Dr. {doctor} abhi chamber me a gaye hain.\n"
            f"Aapka token #{entry.token_number} — kripya clinic pahunch jaiye.\n"
        )
        out.append(
            {
                "token": entry.token_number,
                "patient_name": entry.patient_name,
                "whatsapp_url": f"https://wa.me/91{phone[-10:]}?text={_quote(msg)}",
            }
        )
    return out


# ── E-02 · Token hold & return ──────────────────────────────────────────────


@router.post("/queue/hold", include_in_schema=False)
async def queue_hold(request: Request):
    """Park a called patient who stepped out (washroom / reception).

    Body: ``{entry_id, reason?}``. The patient KEEPS their place in principle —
    see :func:`queue_requeue` for how they come back.
    """
    _sess(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    entry_id = str((body or {}).get("entry_id") or "").strip()
    reason = str((body or {}).get("reason") or "").strip()[:200] or "Patient stepped out"
    if not entry_id:
        return JSONResponse({"ok": False, "error": "entry_id chahiye."}, status_code=400)

    async with async_session_factory() as session:
        entry = await _load_entry(session, entry_id)
        if entry is None:
            return JSONResponse({"ok": False, "error": "Queue entry nahi mili."}, status_code=404)

        status = (entry.status or "").upper()
        if status not in HOLDABLE_STATUSES:
            return JSONResponse(
                {
                    "ok": False,
                    "error": f"Is entry ko hold nahi kar sakte (status: {status}).",
                },
                status_code=400,
            )

        entry.status = "HOLD"
        entry.held_at = datetime.now(timezone.utc)
        entry.hold_reason = reason
        entry.updated_by = "chamber"
        await session.commit()
        token = entry.token_number
        name = entry.patient_name

    return {
        "ok": True,
        "token": token,
        "status": "HOLD",
        "message": f"Token #{token} ({name}) hold par — wapas aate hi agla number milega.",
    }


@router.post("/queue/requeue", include_in_schema=False)
async def queue_requeue(request: Request):
    """Bring a held patient back at **Next + 1** — not at the back of the line.

    How the position is chosen (E-02):
      * the patient currently inside the chamber is the anchor;
      * the returning patient is placed halfway between that anchor and the
        next waiting token, using a fractional ``sort_key`` — so nobody else's
        number has to be rewritten (O(1) insert, no shifting);
      * the first return is free, a second one goes to the back (abuse guard).
    """
    _sess(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    entry_id = str((body or {}).get("entry_id") or "").strip()
    if not entry_id:
        return JSONResponse({"ok": False, "error": "entry_id chahiye."}, status_code=400)

    async with async_session_factory() as session:
        entry = await _load_entry(session, entry_id)
        if entry is None:
            return JSONResponse({"ok": False, "error": "Queue entry nahi mili."}, status_code=404)
        if (entry.status or "").upper() != "HOLD":
            return JSONResponse(
                {"ok": False, "error": f"Ye entry hold par nahi hai (status: {entry.status})."},
                status_code=400,
            )

        siblings = await _active_entries(session, str(entry.clinic_id or ""), str(entry.doctor_id or ""))
        inside = [e for e in siblings if (e.status or "").upper() == "IN_PROGRESS"]
        waiting = [
            e for e in siblings
            if (e.status or "").upper() in ("WAITING", "CALLED") and str(e.id) != str(entry.id)
        ]

        already_returned = int(entry.requeue_count or 0)
        position_note = "Aapka number agla hai."

        if already_returned >= MAX_FREE_REQUEUES:
            # Second return → back of the line, honestly explained.
            keys = [_entry_key(e) for e in waiting] or [0.0]
            new_key = max(keys) + 1.0
            position_note = "Doosri baar hold hua — ab line ke aakhir me."
        elif inside:
            anchor = max(_entry_key(e) for e in inside)
            next_keys = sorted(_entry_key(e) for e in waiting if _entry_key(e) > anchor)
            if next_keys:
                new_key = (anchor + next_keys[0]) / 2.0
            else:
                new_key = anchor + 0.5
            position_note = "Wapas aapki jagah — chamber ke turant baad."
        else:
            keys = sorted(_entry_key(e) for e in waiting)
            new_key = (keys[0] - 0.5) if keys else float(entry.token_number or 1)
            position_note = "Wapas aapki jagah — line ke shuru me."

        entry.sort_key = float(new_key)
        entry.status = "WAITING"
        entry.requeue_count = already_returned + 1
        entry.called_at = None
        entry.updated_by = "chamber"
        await session.commit()
        token = entry.token_number
        name = entry.patient_name
        ahead = sum(1 for e in waiting if _entry_key(e) < float(new_key))

    return {
        "ok": True,
        "token": token,
        "patients_ahead": ahead,
        "position_note": position_note,
        "message": f"Token #{token} ({name}) wapas line me — aapse {ahead} patient aage.",
    }


# ── E-07 · No-show detection ────────────────────────────────────────────────


async def _sweep_no_shows(
    session,
    clinic_id: str,
    doctor_id: str,
    entries: list[QueueEntryModel] | None = None,
    now: datetime | None = None,
) -> tuple[list[QueueEntryModel], list[QueueEntryModel]]:
    """Mark CALLED-but-absent patients as NO_SHOW. Returns (absent, present).

    Called automatically before every live-EWT read, because the honest fix for
    a stale countdown is not a nicer number — it is removing the person who is
    not there. Nobody is swept unless the reception *called* them and they did
    not appear within :data:`ewt.NO_SHOW_AFTER_MINUTES`.

    The verdict itself is pure (``ewt.sweep_no_shows``); this function only
    persists it, so the rule stays unit-testable without a database.
    """
    rows = entries if entries is not None else await _active_entries(session, clinic_id, doctor_id)
    absent, present = ewt.sweep_no_shows(rows, now=now)
    if not absent:
        return [], list(rows)
    moment = now or datetime.now(timezone.utc)
    for entry in absent:
        entry.status = "NO_SHOW"
        entry.updated_by = "no_show_sweep"
        entry.updated_at = moment
    await session.commit()
    logger.info("no-show sweep: %d patient(s) marked absent", len(absent))
    return absent, present


@router.post("/queue/sweep-no-shows", include_in_schema=False)
async def queue_sweep_no_shows(request: Request):
    """Run the no-show check now and report what changed.

    Body (optional): ``{threshold_minutes: 8}``.

    Safe to call repeatedly: an entry is only swept once, and the guard is the
    status transition CALLED → NO_SHOW, which no other state satisfies.
    """
    sess = _sess(request)
    clinic_id = await _resolve_clinic_id(sess)
    doctor_id = _doctor_id(sess)
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        threshold = int((body or {}).get("threshold_minutes") or ewt.NO_SHOW_AFTER_MINUTES)
    except (TypeError, ValueError):
        threshold = ewt.NO_SHOW_AFTER_MINUTES
    threshold = max(1, min(120, threshold))

    async with async_session_factory() as session:
        rows = await _active_entries(session, clinic_id, doctor_id)
        absent, present = ewt.sweep_no_shows(rows, threshold=threshold)
        moment = datetime.now(timezone.utc)
        for entry in absent:
            entry.status = "NO_SHOW"
            entry.updated_by = "no_show_sweep"
            entry.updated_at = moment
        if absent:
            await session.commit()

        marked = [
            {
                "entry_id": str(e.id),
                "token_number": e.token_number,
                "patient_name": e.patient_name or "",
                "waited_minutes": int(round(ewt.minutes_since_called(e, now=moment) or 0)),
                "note": ewt.no_show_recovery_note(
                    e.token_number, ewt.minutes_since_called(e, now=moment)
                ),
            }
            for e in absent
        ]
        still_waiting = sum(
            1 for e in present if (e.status or "").upper() in ("WAITING", "CALLED")
        )

    return {
        "ok": True,
        "threshold_minutes": threshold,
        "marked": marked,
        "count": len(marked),
        "waiting": still_waiting,
        "message": (
            f"{len(marked)} patient 8 min me nahi pahunche — NO_SHOW mark kiye. "
            "Baaki queue apne aap update ho gayi."
            if marked
            else "Sab patients hazir hain — koi no-show nahi."
        ),
    }


@router.post("/queue/recall", include_in_schema=False)
async def queue_recall(request: Request):
    """Bring a NO_SHOW (or HOLD) patient back into the line — the late arrival.

    Body: ``{entry_id, at_front?}``.

    A patient who misses their call is usually just stuck in traffic, not gone.
    The default is the back of the line (fair to everyone who did show up); the
    receptionist can pass ``at_front: true`` for a genuine mistake on our side,
    which puts them back at Next + 1 using the same midpoint trick as E-02.
    """
    _sess(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    entry_id = str((body or {}).get("entry_id") or "").strip()
    at_front = bool((body or {}).get("at_front"))
    if not entry_id:
        return JSONResponse({"ok": False, "error": "entry_id chahiye."}, status_code=400)

    async with async_session_factory() as session:
        entry = await _load_entry(session, entry_id)
        if entry is None:
            return JSONResponse({"ok": False, "error": "Queue entry nahi mili."}, status_code=404)

        status = (entry.status or "").upper()
        if status not in ("NO_SHOW", "HOLD"):
            return JSONResponse(
                {"ok": False, "error": f"Ye entry recall nahi ho sakti (status: {status})."},
                status_code=400,
            )

        siblings = await _active_entries(
            session, str(entry.clinic_id or ""), str(entry.doctor_id or "")
        )
        inside = [e for e in siblings if (e.status or "").upper() == "IN_PROGRESS"]
        waiting = [
            e for e in siblings
            if (e.status or "").upper() in ("WAITING", "CALLED") and str(e.id) != str(entry.id)
        ]

        if at_front and inside:
            anchor = max(_entry_key(e) for e in inside)
            later = sorted(_entry_key(e) for e in waiting if _entry_key(e) > anchor)
            new_key = (anchor + later[0]) / 2.0 if later else anchor + 0.5
            note = "Wapas line me — chamber ke turant baad."
        else:
            keys = [_entry_key(e) for e in waiting]
            new_key = (max(keys) + 1.0) if keys else float(entry.token_number or 1)
            note = "Wapas line me — line ke aakhir me."

        entry.sort_key = float(new_key)
        entry.status = "WAITING"
        entry.held_at = None
        entry.hold_reason = ""
        entry.called_at = None
        entry.updated_by = "recall"
        await session.commit()
        token = entry.token_number
        name = entry.patient_name
        ahead = sum(1 for e in waiting if _entry_key(e) < float(new_key))

    return {
        "ok": True,
        "token": token,
        "patients_ahead": ahead,
        "position_note": note,
        "message": f"Token #{token} ({name}) wapas line me — aapse {ahead} patient aage.",
    }


# ── B4 · Live EWT feed for the doctor's screen ──────────────────────────────


@router.get("/queue-ewt", include_in_schema=False)
async def queue_ewt(request: Request):
    """Per-patient wait estimate + delay badge for the live view."""
    sess = _sess(request)
    clinic_id = await _resolve_clinic_id(sess)
    doctor_id = _doctor_id(sess)

    async with async_session_factory() as session:
        row = await _chamber(session, clinic_id, doctor_id)
        state = _chamber_state(row)
        # E-07: sweep before reading. A patient who never showed up must not
        # keep inflating everybody's EWT — the countdown has to be honest even
        # when nobody clicks anything.
        swept, entries = await _sweep_no_shows(session, clinic_id, doctor_id)
        history = await _history(session, clinic_id, doctor_id)

    avg_minutes, samples = ewt.avg_service_minutes(history)
    inside = next((e for e in entries if (e.status or "").upper() == "IN_PROGRESS"), None)
    severity = ewt.delay_severity(inside, avg_minutes)

    feed: list[dict[str, Any]] = []
    queue_before: list[QueueEntryModel] = []
    for entry in entries:
        status = (entry.status or "").upper()
        if status == "IN_PROGRESS":
            feed.append(
                {
                    "entry_id": str(entry.id),
                    "token_number": entry.token_number,
                    "patient_name": entry.patient_name,
                    "status": status,
                    "wait_minutes": 0,
                    "confidence": "high",
                    "visit_label": ewt.VISIT_TYPE_LABEL.get(
                        (entry.visit_type or "").lower(), "Consultation"
                    ),
                    "inside_minutes": int(round(ewt.elapsed_since_started(entry))),
                    "delay_severity": severity,
                }
            )
            continue

        estimate = ewt.estimate_wait(
            ahead=queue_before,
            avg_minutes=avg_minutes,
            samples=samples,
            current=inside,
            chamber_open=state["chamber_open"],
            me=entry,
        )
        feed.append(
            {
                "entry_id": str(entry.id),
                "token_number": entry.token_number,
                "patient_name": entry.patient_name,
                "status": status,
                "wait_minutes": estimate.minutes,
                "confidence": estimate.confidence,
                "visit_label": ewt.VISIT_TYPE_LABEL.get(
                    (entry.visit_type or "").lower(), "Consultation"
                ),
                "note": estimate.note,
                "delay_severity": severity,
            }
        )
        queue_before.append(entry)

    return {
        "ok": True,
        "clinic_id": clinic_id,
        "doctor_id": doctor_id,
        **state,
        "avg_service_minutes": round(avg_minutes, 1),
        "samples": samples,
        "delay_severity": severity,
        "queue": feed,
        "no_shows": [
            {
                "entry_id": str(e.id),
                "token_number": e.token_number,
                "patient_name": e.patient_name or "",
                "waited_minutes": int(round(ewt.minutes_since_called(e) or 0)),
                "note": ewt.no_show_recovery_note(
                    e.token_number, ewt.minutes_since_called(e)
                ),
            }
            for e in swept
        ],
        "counts": {
            "waiting": sum(1 for e in entries if (e.status or "").upper() in ("WAITING", "CALLED")),
            "in_progress": 1 if inside else 0,
            "on_hold": sum(1 for e in entries if (e.status or "").upper() == "HOLD"),
            "no_show": len(swept),
        },
    }


# ── E-03b · Leave-now link (reception one tap, no gateway) ──────────────────


@router.post("/queue/leave-now", include_in_schema=False)
async def queue_leave_now(request: Request):
    """Return a WhatsApp link telling a patient to start moving.

    Body: ``{entry_id, travel_minutes?, distance_km?, patient_lat?, patient_lon?}``.

    The browser opens the link; nothing is sent from the server, so this works
    inside the PythonAnywhere outbound whitelist.

    Since E-03c the advice is transit-aware: when the caller supplies the
    patient's coordinates (the tracking page can read them with permission) the
    message says *when* to leave — ``wait ≤ travel + buffer`` — instead of a
    flat "ab niklo" that sent a patient 25 minutes away into a 6-minute wait.
    """
    _sess(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    entry_id = str((body or {}).get("entry_id") or "").strip()
    if not entry_id:
        return JSONResponse({"ok": False, "error": "entry_id chahiye."}, status_code=400)

    async with async_session_factory() as session:
        entry = await _load_entry(session, entry_id)
        if entry is None:
            return JSONResponse({"ok": False, "error": "Queue entry nahi mili."}, status_code=404)
        entries = await _active_entries(session, str(entry.clinic_id or ""), str(entry.doctor_id or ""))
        history = await _history(session, str(entry.clinic_id or ""), str(entry.doctor_id or ""))
        clinic_lat = clinic_lon = None
        try:
            from src.infrastructure.clinic.models.clinic_model import ClinicModel

            # Compare as a real UUID, not a cast string: SQLite stores UUID
            # columns as 32-char hex without dashes, so `str(uuid)` never
            # matches and the travel estimate would silently never appear.
            clinic_uuid = uuid.UUID(str(entry.clinic_id or ""))
            row = await session.execute(
                sa.select(ClinicModel.latitude, ClinicModel.longitude).where(
                    ClinicModel.id == clinic_uuid
                )
            )
            found = row.first()
            if found:
                clinic_lat, clinic_lon = found[0], found[1]
        except Exception as exc:  # pragma: no cover - coordinates are best-effort
            logger.debug("clinic coordinates lookup failed: %s", exc)
        token = entry.token_number
        name = entry.patient_name

    phone = _phone_of(entry, await _phones_for([entry]))

    avg_minutes, samples = ewt.avg_service_minutes(history)
    inside = next((e for e in entries if (e.status or "").upper() == "IN_PROGRESS"), None)
    my_key = _entry_key(next((e for e in entries if str(e.id) == entry_id), entry))
    ahead = [
        e for e in entries
        if (e.status or "").upper() in ("WAITING", "CALLED") and _entry_key(e) < my_key
    ]
    estimate = ewt.estimate_wait(
        ahead=ahead, avg_minutes=avg_minutes, samples=samples, current=inside
    )

    # ── travel time: explicit minutes win, else GPS from the tracking page ──
    travel_minutes: int | None = None
    distance = None
    raw_travel = (body or {}).get("travel_minutes")
    if str(raw_travel or "").strip():
        try:
            travel_minutes = max(0, int(raw_travel))
        except (TypeError, ValueError):
            travel_minutes = None
    explicit_km = (body or {}).get("distance_km")
    if travel_minutes is None:
        distance = travel.distance_km(
            (body or {}).get("patient_lat"),
            (body or {}).get("patient_lon"),
            clinic_lat,
            clinic_lon,
        )
        if distance is None and str(explicit_km or "").strip():
            try:
                distance = float(explicit_km)
            except (TypeError, ValueError):
                distance = None
        if distance is not None:
            travel_minutes = travel.travel_minutes(distance)

    decision = travel.leave_decision(estimate.minutes, travel_minutes)
    msg = travel.departure_message(token, estimate.minutes, travel_minutes)

    return {
        "ok": True,
        "patients_ahead": estimate.patients_ahead,
        "wait_minutes": estimate.minutes,
        "has_travel": decision["has_travel"],
        "travel_minutes": travel_minutes,
        "distance_km": round(distance, 1) if distance is not None else None,
        "urgency": decision["urgency"],
        "slack_minutes": decision["slack_minutes"],
        # Backwards compatible: this used to be the only signal.
        "should_leave": decision["should_leave"],
        "phone_found": bool(phone),
        "whatsapp_url": f"https://wa.me/91{phone[-10:]}?text={_quote(msg)}" if phone else "",
        "message": msg,
    }


# ── small helpers ───────────────────────────────────────────────────────────


async def _load_entry(session, entry_id: str) -> QueueEntryModel | None:
    """Fetch a queue entry by UUID or by its human string id."""
    try:
        return await session.get(QueueEntryModel, uuid.UUID(entry_id))
    except (ValueError, AttributeError, TypeError):
        pass
    row = await session.execute(
        sa.select(QueueEntryModel).where(sa.cast(QueueEntryModel.id, sa.String) == entry_id).limit(1)
    )
    return row.scalars().first()


def _phone_of(entry: QueueEntryModel, phones: dict[str, str] | None = None) -> str:
    """Phone for a WhatsApp link, from a pre-fetched {patient_id: phone} map."""
    if not phones:
        return ""
    return str(phones.get(str(entry.patient_id)) or "").strip()


async def _phones_for(entries: list[QueueEntryModel]) -> dict[str, str]:
    """Batch phone lookup — one query for the whole waiting list."""
    ids = {str(e.patient_id) for e in entries if e.patient_id}
    if not ids:
        return {}
    try:
        from src.infrastructure.patient.models.patient_model import PatientModel

        async with async_session_factory() as session:
            rows = await session.execute(
                sa.select(PatientModel.patient_id, PatientModel.phone).where(
                    PatientModel.patient_id.in_(list(ids))
                )
            )
            return {str(pid): (phone or "").strip() for pid, phone in rows.all()}
    except Exception as exc:  # pragma: no cover - links are best-effort
        logger.debug("phone lookup failed: %s", exc)
        return {}


def _quote(text: str) -> str:
    from urllib.parse import quote

    return quote(text, safe="")
