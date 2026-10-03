"""Slot booking + emergency override routes (BLOCK 3 · SLT-01/02/03, E-08).

Why slots exist in a live-queue product
---------------------------------------
The product's own mantra is *"live queue > khaali appointment slot"*, because a
slot pretends every patient takes the same 20 minutes. But some patients need a
fixed time — a working patient who can only come at 2:30, a follow-up that must
wait for a lab report, a patient travelling from another city.

So a slot here is a **capacity reservation inside the same live queue**, never
a separate queue. The patient gets a real token and a real EWT, and the grid
shows what the queue looks like at that time:

    2:30 PM · 1/2 booked · us waqt tak queue clear hone ka anumaan 🟢 high

Two invariants this module protects:

  * **A slot never oversells.** Capacity is checked against the real bookings in
    ``queue_entries.slot_id``, not against a stored counter — so a cancelled
    booking frees its place immediately.
  * **An emergency never consumes a routine token** (E-08). ``#E-1`` comes from
    its own sequence, so the routine patients do not see a gap and conclude
    that somebody was skipped.

Like the rest of the queue engine this module is additive and borrows the OPD
session guard lazily, so ``opd_routes.py`` (4,000+ lines) stays untouched.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date as date_type
from datetime import datetime, time, timedelta, timezone
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from src.domain.queue import ewt, token_label
from src.infrastructure.queue.models.appointment_slot_model import AppointmentSlotModel
from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel
from src.shared.infrastructure.database import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/opd/api/slots", tags=["Slot Booking"])

#: Longest single slot we will create; anything longer is a typo, not a clinic.
MAX_SLOT_MINUTES = 240
#: Upper bound on a bulk generation, so a slip of the keyboard cannot write
#: thousands of rows.
MAX_SLOTS_PER_GENERATION = 80

ACTIVE_STATUSES = ("WAITING", "CALLED", "HOLD", "IN_PROGRESS")
#: Bookings that still occupy a slot's capacity.
OCCUPYING_STATUSES = ("WAITING", "CALLED", "HOLD", "IN_PROGRESS")


# ── session / scope helpers (same pattern as queue_engine_routes) ───────────


def _sess(request: Request) -> dict:
    from src.presentation.opd.routes.opd_routes import _require_opd_session  # lazy

    return _require_opd_session(request)


async def _resolve_clinic_id(sess: dict) -> str:
    from src.presentation.queue_engine.routes.queue_engine_routes import (
        _resolve_clinic_id as resolve,
    )

    return await resolve(sess)


def _doctor_id(sess: dict) -> str:
    return str(sess.get("doctor_id") or "chief")


def _today() -> date_type:
    return datetime.now(timezone.utc).date()


# ── time helpers ────────────────────────────────────────────────────────────


def _parse_clock(value: Any) -> time | None:
    """``"14:30"`` → ``time``, reusing the clinic-hours parser (never raises)."""
    from src.domain.clinic import opening_hours

    return opening_hours.parse_time(value)


def _fmt(clock: time) -> str:
    return clock.strftime("%H:%M")


def _parse_day(value: Any, default: date_type | None = None) -> date_type | None:
    from src.domain.clinic import opening_hours

    if value is None or str(value).strip() == "":
        return default
    return opening_hours.parse_date(value)


def _parse_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


# ── reading slots ───────────────────────────────────────────────────────────


async def _booked_counts(session, slot_ids: list[str]) -> dict[str, int]:
    """How many live bookings each slot holds — one query, not one per slot.

    Counted from ``queue_entries`` rather than a stored counter so a cancelled
    or no-show booking frees its place the moment it changes state.
    """
    if not slot_ids:
        return {}
    rows = await session.execute(
        sa.select(QueueEntryModel.slot_id, sa.func.count(QueueEntryModel.id))
        .where(
            QueueEntryModel.slot_id.in_(slot_ids),
            QueueEntryModel.status.in_(OCCUPYING_STATUSES),
        )
        .group_by(QueueEntryModel.slot_id)
    )
    return {str(sid): int(count) for sid, count in rows.all() if sid}


async def _day_slots(
    session, clinic_id: str, doctor_id: str, day: date_type
) -> list[AppointmentSlotModel]:
    stmt = sa.select(AppointmentSlotModel).where(
        AppointmentSlotModel.slot_date == day
    )
    if clinic_id:
        stmt = stmt.where(AppointmentSlotModel.clinic_id == clinic_id)
    if doctor_id:
        stmt = stmt.where(AppointmentSlotModel.doctor_id == doctor_id)
    stmt = stmt.order_by(AppointmentSlotModel.start_time.asc())
    return list((await session.execute(stmt)).scalars().all())


async def _slot_queue_context(session, clinic_id: str, doctor_id: str) -> dict[str, Any]:
    """Live queue state, so a slot is never shown on its own (blueprint B5).

    Returns ``avg_minutes``/``samples``/``velocity``/``chamber_open`` — the same
    inputs the EWT engine uses, so the grid and the patient page can never
    disagree about how fast today is running.
    """
    from src.presentation.queue_engine.routes.queue_engine_routes import (
        _chamber,
        _chamber_state,
        _history,
    )

    row = await _chamber(session, clinic_id, doctor_id)
    state = _chamber_state(row)
    history = await _history(session, clinic_id, doctor_id)
    avg_minutes, samples = ewt.avg_service_minutes(history)
    pace = ewt.recent_velocity(history, avg_minutes)
    return {
        "chamber_open": state["chamber_open"],
        "avg_service_minutes": round(avg_minutes, 1),
        "samples": samples,
        "velocity": round(pace, 2),
    }


def _slot_public(
    slot: AppointmentSlotModel,
    booked: int,
    context: dict[str, Any],
    counts: dict[str, int],
    now: datetime | None = None,
) -> dict[str, Any]:
    """One grid row: the slot, its load, and the live queue behind it."""
    capacity = max(1, int(slot.capacity or 1))
    remaining = max(0, capacity - booked)
    waiting = int(counts.get("waiting") or 0)

    forecast, confidence = _slot_forecast(slot, context, waiting, now)

    return {
        "id": str(slot.id),
        "slot_date": slot.slot_date.isoformat() if slot.slot_date else "",
        "start_time": slot.start_time,
        "end_time": slot.end_time,
        "window": slot.window_label,
        "capacity": capacity,
        "booked": booked,
        "remaining": remaining,
        "is_full": remaining <= 0,
        "is_active": bool(slot.is_active),
        "note": slot.note or "",
        "forecast": forecast,
        "confidence": confidence,
        "queue": {
            "waiting": waiting,
            "chamber_open": bool(context.get("chamber_open")),
            "avg_service_minutes": context.get("avg_service_minutes"),
        },
    }


def _slot_forecast(
    slot: AppointmentSlotModel,
    context: dict[str, Any],
    waiting: int,
    now: datetime | None = None,
) -> tuple[str, str]:
    """Will the queue have cleared by the time this window arrives?

    Blueprint B5's rule is that a slot never appears alone — it carries the
    live queue and an EWT confidence. The honest calculation is a throughput
    comparison, not a guess:

        patients the doctor can still see before the window
            = minutes until the window / learned average  ×  today's pace

    If that is at least the number of people waiting, the queue will have
    cleared. If it is fewer, the leftover count is what the patient should
    expect to find ahead of them.

    Returns ``(forecast_text, confidence)``.
    """
    if not context.get("chamber_open"):
        return "OPD abhi shuru nahi hua — wait count baad me lagega.", "low"

    avg = float(context.get("avg_service_minutes") or 7.0)
    pace = float(context.get("velocity") or 1.0)
    samples = int(context.get("samples") or 0)
    moment = now or datetime.now(timezone.utc)

    start_clock = _parse_clock(slot.start_time)
    if start_clock is None or slot.slot_date is None:
        return "Is slot ke waqt ka anumaan nahi lag sakta.", "low"

    from src.domain.clinic import opening_hours

    slot_moment = datetime.combine(
        slot.slot_date, start_clock, tzinfo=opening_hours.CLINIC_TZ
    )
    minutes_until = (slot_moment - moment).total_seconds() / 60.0

    if minutes_until <= 0:
        # The window is now (or already past) — report the real queue instead
        # of a forecast about a moment that has gone.
        if waiting == 0:
            return "Queue khaali hai — abhi turant turn.", ewt.eta_confidence(0, samples)
        confidence = ewt.eta_confidence(waiting, samples)
        minutes = max(ewt.MIN_EWT_MINUTES, int(round(waiting * avg * pace)))
        return (
            f"Abhi {waiting} patient aage · ~{minutes} min ({_confidence_hi(confidence)})",
            confidence,
        )

    # Throughput available before the window opens.
    per_patient = max(1.0, avg * pace)
    clearable = minutes_until / per_patient
    confidence = ewt.eta_confidence(waiting, samples)

    if waiting <= clearable:
        if waiting == 0:
            return (
                "Queue already khaali — jaise hi aayenge turn milega.",
                ewt.eta_confidence(0, samples),
            )
        return (
            f"Us waqt tak queue clear hone ka anumaan — "
            f"{waiting} patient {int(round(minutes_until))} min me nipat jayenge "
            f"({_confidence_hi(confidence)})",
            confidence,
        )

    leftover = max(1, int(round(waiting - clearable)))
    return (
        f"Us waqt tak ~{leftover} patient aage reh sakte hain "
        f"(~{int(round(leftover * avg * pace))} min) ({_confidence_hi(confidence)})",
        confidence,
    )


def _confidence_hi(confidence: str) -> str:
    return {
        "high": "🟢 bharosemand",
        "medium": "🟡 theek",
        "low": "⚪ anumaan",
    }.get(confidence, "⚪ anumaan")


# ── SLT-01 · slot CRUD ──────────────────────────────────────────────────────


@router.get("", include_in_schema=False)
async def list_slots(
    request: Request,
    date: str = Query(default="", description="YYYY-MM-DD (default: today)"),
):
    """The doctor's slot grid for one day, with live load and EWT confidence."""
    sess = _sess(request)
    clinic_id = await _resolve_clinic_id(sess)
    doctor_id = _doctor_id(sess)
    day = _parse_day(date, _today())
    if day is None:
        return JSONResponse({"ok": False, "error": "Date samajh nahi aayi."}, status_code=400)

    async with async_session_factory() as session:
        slots = await _day_slots(session, clinic_id, doctor_id, day)
        booked = await _booked_counts(session, [str(s.id) for s in slots])
        context = await _slot_queue_context(session, clinic_id, doctor_id)
        counts = await _queue_counts(session, clinic_id, doctor_id)

    now = datetime.now(timezone.utc)
    rows = [
        _slot_public(s, booked.get(str(s.id), 0), context, counts, now) for s in slots
    ]
    return {
        "ok": True,
        "clinic_id": clinic_id,
        "doctor_id": doctor_id,
        "date": day.isoformat(),
        "slots": rows,
        "total": len(rows),
        "open_slots": sum(1 for r in rows if r["remaining"] > 0 and r["is_active"]),
        "context": context,
        "message": (
            f"{len(rows)} slot {day.isoformat()} ke liye."
            if rows
            else "Is din ke liye koi slot nahi bana — neeche se bana lein."
        ),
    }


async def _queue_counts(session, clinic_id: str, doctor_id: str) -> dict[str, int]:
    from src.presentation.queue_engine.routes.queue_engine_routes import _active_entries

    entries = await _active_entries(session, clinic_id, doctor_id)
    return {
        "waiting": sum(
            1 for e in entries if (e.status or "").upper() in ("WAITING", "CALLED")
        ),
        "in_progress": sum(
            1 for e in entries if (e.status or "").upper() == "IN_PROGRESS"
        ),
        "on_hold": sum(1 for e in entries if (e.status or "").upper() == "HOLD"),
    }


@router.post("", include_in_schema=False)
async def create_slots(request: Request):
    """Create a slot, or a whole day's worth in one call.

    Body::

        Single   {"date": "2026-10-05", "start_time": "14:30",
                  "end_time": "14:50", "capacity": 1, "note": ""}

        Bulk     {"date": "2026-10-05", "from_time": "09:00", "to_time": "12:00",
                  "duration_minutes": 20, "capacity": 1}

    Idempotent per ``(clinic, doctor, date, start_time)``: re-running a bulk
    generate updates nothing and creates nothing new, so a receptionist can
    safely press it twice.
    """
    sess = _sess(request)
    clinic_id = await _resolve_clinic_id(sess)
    doctor_id = _doctor_id(sess)
    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body or {}

    day = _parse_day(body.get("date"), _today())
    if day is None:
        return JSONResponse({"ok": False, "error": "Date samajh nahi aayi."}, status_code=400)

    try:
        capacity = max(1, min(20, int(body.get("capacity") or 1)))
    except (TypeError, ValueError):
        capacity = 1
    note = str(body.get("note") or "").strip()[:200]
    created_by = str(sess.get("name") or "clinic")

    # ── build the list of windows to create ──
    windows: list[tuple[time, time]] = []
    bulk_from = _parse_clock(body.get("from_time"))
    bulk_to = _parse_clock(body.get("to_time"))
    if bulk_from and bulk_to:
        try:
            duration = int(body.get("duration_minutes") or 20)
        except (TypeError, ValueError):
            duration = 20
        duration = max(5, min(MAX_SLOT_MINUTES, duration))
        cursor = bulk_from
        while len(windows) < MAX_SLOTS_PER_GENERATION:
            end = _add_minutes(cursor, duration)
            if end <= cursor:  # wrapped past midnight — stop
                break
            if _minutes_between(bulk_from, end) > _minutes_between(bulk_from, bulk_to):
                break
            windows.append((cursor, end))
            cursor = end
    else:
        start = _parse_clock(body.get("start_time"))
        end = _parse_clock(body.get("end_time"))
        if start is None:
            return JSONResponse(
                {"ok": False, "error": "start_time ya from_time/to_time chahiye."},
                status_code=400,
            )
        if end is None:
            end = _add_minutes(start, 20)
        if end <= start:
            return JSONResponse(
                {"ok": False, "error": "end_time start_time ke baad hona chahiye."},
                status_code=400,
            )
        if _minutes_between(start, end) > MAX_SLOT_MINUTES:
            return JSONResponse(
                {"ok": False, "error": f"Ek slot {MAX_SLOT_MINUTES} min se lamba nahi ho sakta."},
                status_code=400,
            )
        windows.append((start, end))

    if not windows:
        return JSONResponse(
            {"ok": False, "error": "Koi slot window nahi bani — times check karein."},
            status_code=400,
        )

    created: list[str] = []
    skipped = 0
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        existing_rows = await session.execute(
            sa.select(AppointmentSlotModel.start_time).where(
                AppointmentSlotModel.clinic_id == clinic_id,
                AppointmentSlotModel.doctor_id == doctor_id,
                AppointmentSlotModel.slot_date == day,
            )
        )
        taken = {str(r[0]) for r in existing_rows.all()}

        for start, end in windows:
            start_label = _fmt(start)
            if start_label in taken:
                skipped += 1
                continue
            taken.add(start_label)
            session.add(
                AppointmentSlotModel(
                    id=uuid.uuid4(),
                    clinic_id=clinic_id,
                    doctor_id=doctor_id,
                    service_code="OPD",
                    slot_date=day,
                    start_time=start_label,
                    end_time=_fmt(end),
                    capacity=capacity,
                    is_active=True,
                    note=note,
                    created_by=created_by,
                    created_at=now,
                    updated_at=now,
                )
            )
            created.append(start_label)
        await session.commit()

    return {
        "ok": True,
        "date": day.isoformat(),
        "created": len(created),
        "skipped": skipped,
        "times": created,
        "message": (
            f"{len(created)} slot banaye"
            + (f", {skipped} pehle se the." if skipped else ".")
        ),
    }


@router.post("/{slot_id}/toggle", include_in_schema=False)
async def toggle_slot(request: Request, slot_id: str):
    """Open or close one slot for booking, without deleting it."""
    _sess(request)
    async with async_session_factory() as session:
        slot = await _load_slot(session, slot_id)
        if slot is None:
            return JSONResponse({"ok": False, "error": "Slot nahi mila."}, status_code=404)
        slot.is_active = not bool(slot.is_active)
        await session.commit()
        state = slot.is_active
        window = slot.window_label

    return {
        "ok": True,
        "is_active": state,
        "window": window,
        "message": f"Slot {window} {'khul gaya' if state else 'band kar diya'}.",
    }


@router.post("/{slot_id}/delete", include_in_schema=False)
async def delete_slot(request: Request, slot_id: str):
    """Delete a slot — refused once a patient holds a booking in it.

    Deleting a slot someone has already booked would strand that patient with a
    token and no window, so the honest answer is to refuse and say why.
    """
    _sess(request)
    async with async_session_factory() as session:
        slot = await _load_slot(session, slot_id)
        if slot is None:
            return JSONResponse({"ok": False, "error": "Slot nahi mila."}, status_code=404)
        booked = (await _booked_counts(session, [str(slot.id)])).get(str(slot.id), 0)
        if booked:
            return JSONResponse(
                {
                    "ok": False,
                    "error": (
                        f"Is slot me {booked} patient booked hai — pehle unhe "
                        "shift karein ya slot band kar dein (delete na karein)."
                    ),
                },
                status_code=400,
            )
        window = slot.window_label
        await session.delete(slot)
        await session.commit()

    return {"ok": True, "window": window, "message": f"Slot {window} delete ho gaya."}


async def _load_slot(session, slot_id: str):
    slot_uuid = _parse_uuid(slot_id)
    if slot_uuid is None:
        return None
    return await session.get(AppointmentSlotModel, slot_uuid)


def _add_minutes(clock: time, minutes: int) -> time:
    total = clock.hour * 60 + clock.minute + int(minutes)
    total %= 24 * 60
    return time(hour=total // 60, minute=total % 60)


def _minutes_between(start: time, end: time) -> int:
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)


# ── SLT-02 · book a slot into the live queue ────────────────────────────────


async def _next_routine_token(session, clinic_id: str, doctor_id: str) -> int:
    """Next routine OPD token for this clinic + doctor + day (BUG-01 partition).

    Emergency entries are excluded on purpose (E-08): they carry their own
    ``E`` sequence, and letting one bump ``MAX(token_number)`` would make the
    routine numbers skip — every waiting patient would then assume somebody was
    called ahead of them without explanation.
    """
    date_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
    row = await session.execute(
        sa.select(sa.func.coalesce(sa.func.max(QueueEntryModel.token_number), 0)).where(
            QueueEntryModel.clinic_id == clinic_id,
            QueueEntryModel.doctor_id == doctor_id,
            QueueEntryModel.service_code == "OPD",
            QueueEntryModel.visit_type != "emergency",
            QueueEntryModel.visit_id.like(f"VIS-{date_prefix}-%"),
        )
    )
    return int(row.scalar() or 0) + 1


@router.post("/{slot_id}/book", include_in_schema=False)
async def book_slot(request: Request, slot_id: str):
    """Reserve a slot and create the patient's real OPD queue entry.

    Body: ``{name, phone?, age?, problem?, patient_id?}``.

    This is what the reception uses for a patient standing at the desk. It is
    the same operation the public marketplace performs, just authenticated.
    """
    _sess(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body or {}
    name = str(body.get("name") or "").strip()
    if not name:
        return JSONResponse({"ok": False, "error": "Patient ka naam chahiye."}, status_code=400)

    result = await _reserve(
        slot_id=slot_id,
        name=name,
        phone=str(body.get("phone") or "").strip(),
        age=body.get("age"),
        problem=str(body.get("problem") or "").strip(),
        patient_id=str(body.get("patient_id") or "").strip(),
    )
    if not result.get("ok"):
        return JSONResponse(result, status_code=int(result.get("status") or 400))
    return result


async def _reserve(
    slot_id: str,
    name: str,
    phone: str = "",
    age: Any = None,
    problem: str = "",
    patient_id: str = "",
) -> dict[str, Any]:
    """Core reservation: capacity check, then a REAL queue entry.

    Shared by the reception route and the public marketplace booking so the
    capacity rule exists in exactly one place. Returns a dict with ``ok`` and,
    on failure, an ``error`` plus the HTTP ``status`` the caller should use.
    """
    import hashlib

    from src.infrastructure.patient.models.patient_model import PatientModel
    from src.shared.domain.base_entity import uuid7

    slot_uuid = _parse_uuid(slot_id)
    if slot_uuid is None:
        return {"ok": False, "error": "Slot nahi mila.", "status": 404}

    try:
        age_value = int(age) if str(age or "").strip() else 30
    except (TypeError, ValueError):
        age_value = 30
    if age_value < 0 or age_value > 130:
        age_value = 30

    now = datetime.now(timezone.utc)
    date_prefix = now.strftime("%Y%m%d")
    phone_hash = hashlib.sha256(phone.encode()).hexdigest() if phone else ""

    async with async_session_factory() as session:
        slot = await session.get(AppointmentSlotModel, slot_uuid)
        if slot is None:
            return {"ok": False, "error": "Slot nahi mila.", "status": 404}
        if not slot.is_active:
            return {"ok": False, "error": "Ye slot band hai — doosra time chunein.", "status": 400}

        capacity = max(1, int(slot.capacity or 1))
        booked = (await _booked_counts(session, [str(slot.id)])).get(str(slot.id), 0)
        if booked >= capacity:
            return {
                "ok": False,
                "error": f"Ye slot bhar gaya ({booked}/{capacity}) — doosra time chunein.",
                "status": 409,
            }

        clinic_id = str(slot.clinic_id or "")
        doctor_id = str(slot.doctor_id or "chief")

        # ── patient: reuse by phone, else create (same rule as marketplace) ──
        existing = None
        if phone and phone_hash:
            # OPEN-01: tombstones are skipped and followed to their survivor,
            # so a slot booking can never be written against a merged-away row.
            from src.infrastructure.patient.lookup import find_by_phone_resolved

            existing = await find_by_phone_resolved(session, phone_hash)

        if patient_id:
            patient_key = patient_id
            patient_uuid = str(uuid7())
            patient_name = name
            total_visits = 1
        elif existing is not None:
            patient_key = existing.patient_id
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
            patient_key = f"CQ-{date_prefix}-{seq:03d}"
            patient_uuid_obj = uuid7()
            patient_uuid = str(patient_uuid_obj)
            patient_name = name
            total_visits = 1
            session.add(
                PatientModel(
                    id=patient_uuid_obj,
                    patient_id=patient_key,
                    name=name,
                    age=age_value,
                    gender="Not Specified",
                    date_of_birth="",
                    phone=phone,
                    phone_hash=phone_hash,
                    address="",
                    status="active",
                    total_visits=1,
                    last_visit_at=now,
                    reception_inquiry=problem,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )

        token = await _next_routine_token(session, clinic_id, doctor_id)
        visit_type = ewt.classify_visit_type(total_visits=total_visits, age=age_value)
        room = "OPD Room"
        try:
            from src.presentation.marketplace.routes.marketplace_routes import (
                _opd_room_name,
            )

            room = _opd_room_name()
        except Exception:  # pragma: no cover - label is cosmetic
            pass

        entry = QueueEntryModel(
            id=uuid7(),
            clinic_id=clinic_id,
            doctor_id=doctor_id,
            visit_id=f"VIS-{date_prefix}-{uuid7().hex[:6]}",
            patient_id=patient_key,
            patient_uuid=patient_uuid,
            patient_name=patient_name,
            service_code="OPD",
            token_number=token,
            department="OPD",
            room=room,
            status="WAITING",
            priority=0,
            display_order=0,
            sort_key=float(token),
            visit_type=visit_type,
            complexity_weight=ewt.complexity_weight(visit_type),
            slot_id=str(slot.id),
            slot_time=slot.start_time,
            notes=problem or "",
            created_by="slot_booking",
            updated_by="slot_booking",
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(entry)
        await session.commit()

        window = slot.window_label
        remaining = max(0, capacity - (booked + 1))

    return {
        "ok": True,
        "slot_id": slot_id,
        "slot_window": window,
        "slot_time": window.split(" – ")[0] if " – " in window else "",
        "slot_remaining": remaining,
        "token": token,
        "patient_id": patient_key,
        "patient_name": patient_name,
        "visit_type": visit_type,
        "visit_label": ewt.VISIT_TYPE_LABEL.get(visit_type, "Consultation"),
        "room": room,
        "message": (
            f"{name} ka slot {window} par book ho gaya · Token #{token}. "
            "Slot aapki jagah reserve karta hai — asli turn queue ke hisaab se milega."
        ),
    }


# ── E-08 · Emergency override (Code Red) ────────────────────────────────────


@router.post("/emergency", include_in_schema=False)
async def emergency_override(request: Request):
    """Raise a Code Red case: token ``#E-1``, front of the line, siren on screens.

    Body: ``{name, problem?, phone?}``.

    How far forward? **Immediately after the patient inside the chamber**, never
    in front of them — interrupting a consultation already in progress is worse
    for the emergency patient than waiting ninety seconds. Everything still
    WAITING moves back by exactly one place, and the response says so honestly
    so the reception can tell the queue what changed.
    """
    sess = _sess(request)
    clinic_id = await _resolve_clinic_id(sess)
    doctor_id = _doctor_id(sess)
    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body or {}
    name = str(body.get("name") or "").strip() or "Emergency case"
    problem = str(body.get("problem") or "").strip()[:200]
    phone = str(body.get("phone") or "").strip()

    from src.shared.domain.base_entity import uuid7

    now = datetime.now(timezone.utc)
    date_prefix = now.strftime("%Y%m%d")

    async with async_session_factory() as session:
        from src.presentation.queue_engine.routes.queue_engine_routes import (
            _active_entries,
        )

        entries = await _active_entries(session, clinic_id, doctor_id)
        inside = next((e for e in entries if (e.status or "").upper() == "IN_PROGRESS"), None)
        waiting = [e for e in entries if (e.status or "").upper() in ("WAITING", "CALLED")]

        # E tokens have their own sequence so routine numbers never show a gap.
        today_emergencies = await session.execute(
            sa.select(QueueEntryModel.token_number).where(
                QueueEntryModel.clinic_id == clinic_id,
                QueueEntryModel.doctor_id == doctor_id,
                QueueEntryModel.visit_type == "emergency",
                QueueEntryModel.visit_id.like(f"VIS-{date_prefix}-%"),
            )
        )
        token = token_label.next_emergency_token(
            [r[0] for r in today_emergencies.all()]
        )

        # Sort key: right after whoever is inside; otherwise at the very front.
        if inside is not None:
            anchor = float(inside.sort_key if inside.sort_key is not None else (inside.token_number or 0))
            later = sorted(
                float(e.sort_key if e.sort_key is not None else (e.token_number or 0))
                for e in waiting
                if float(e.sort_key if e.sort_key is not None else (e.token_number or 0)) > anchor
            )
            new_key = (anchor + later[0]) / 2.0 if later else anchor + 0.5
            position_note = "Chamber ke turant baad agla number."
        else:
            keys = sorted(
                float(e.sort_key if e.sort_key is not None else (e.token_number or 0))
                for e in waiting
            )
            new_key = (keys[0] - 0.5) if keys else 1.0
            position_note = "Sabse pehle — chamber khaali hai."

        entry = QueueEntryModel(
            id=uuid7(),
            clinic_id=clinic_id,
            doctor_id=doctor_id,
            visit_id=f"VIS-{date_prefix}-{uuid7().hex[:6]}",
            patient_id=f"EMG-{date_prefix}-{token:03d}",
            patient_uuid=str(uuid7()),
            patient_name=name,
            service_code="OPD",
            token_number=token,
            department="Emergency",
            room="Emergency",
            status="WAITING",
            priority=2,  # blueprint B2: 2 = Emergency
            display_order=0,
            sort_key=float(new_key),
            visit_type="emergency",
            complexity_weight=ewt.complexity_weight("emergency"),
            notes=problem,
            created_by="emergency_override",
            updated_by="emergency_override",
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(entry)
        await session.commit()

        # Everyone still waiting moves back by one place — say it honestly.
        affected = len(waiting)
        label = token_label.token_label(token, emergency=True)

    return {
        "ok": True,
        "token": token,
        "token_label": label,
        "emergency": True,
        "position_note": position_note,
        "patients_moved_back": affected,
        "siren": True,
        "message": (
            f"🚨 CODE RED — {label} ({name}). {position_note} "
            f"{affected} waiting patient ek number peeche shift hue."
        ),
        "broadcast": (
            "🚨 Emergency case aa gaya hai. Aapka number safe hai — "
            "wait ~10 min badh sakta hai. Dhanyavaad."
        ),
        "phone": phone,
    }
