"""Cross-clinic referral slip routes (Part F · F-06).

    clinic A ── creates a referral ──▶ signed slip URL
                                          │
              (WhatsApp / reception copies the link)
                                          ▼
    clinic B ── opens /r/<slip> ──▶ accepts ──▶ REAL token in clinic B's queue

Why a signed slip and not just a POST
------------------------------------
Acceptance has to be safe from both directions:

  * **Clinic B cannot be spammed.** Nothing enters its queue until its own
    staff accepts, with their own session. Guessing a URL is not enough.
  * **The slip cannot be forged or replayed.** The token is signed with the
    app secret and time-limited, and the row it points at must still be
    ``PENDING``; a second acceptance of the same slip is refused, so a forwarded
    link cannot mint two tokens.

The slip page itself is public (``/r/<token>``) so it can be opened from
WhatsApp on the receiving doctor's phone — but it shows only what the sending
clinic deliberately chose to share, and it grants nothing on its own.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.domain.queue import ewt, token_label
from src.infrastructure.clinic.models.clinic_model import ClinicModel
from src.infrastructure.clinic.models.referral_model import (
    STATUS_ACCEPTED,
    STATUS_CANCELLED,
    STATUS_DECLINED,
    STATUS_PENDING,
    URGENCY_LABEL,
    URGENCY_ORDER,
    URGENCY_ROUTINE,
    URGENCY_SOON,
    URGENCY_URGENT,
    ReferralModel,
)
from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel
from src.shared.infrastructure.database import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Referrals"])

#: Same secret the tracking tokens use; a separate salt keeps the two token
#: families from ever being interchangeable.
_SECRET_KEY = os.getenv("SECRET_KEY", "gil-clinic-secret-2024-change-in-prod")
_slip_signer = URLSafeTimedSerializer(_SECRET_KEY, salt="clinic-referral-slip-v1")

#: A slip is valid for this many days. Long enough for a patient to find time,
#: short enough that a stale slip does not create a token weeks later.
SLIP_MAX_AGE_DAYS = 14
SLIP_MAX_AGE_SECONDS = SLIP_MAX_AGE_DAYS * 24 * 60 * 60

_TEMPLATES_DIR = Path(__file__).parents[4] / "templates"

VALID_URGENCIES = (URGENCY_ROUTINE, URGENCY_SOON, URGENCY_URGENT)

#: Referral-created tokens are prefixed so the receiving doctor can see at a
#: glance that this patient arrived from another clinic.
TAG_REFERRAL_NOTE = "Referral"


def make_slip_token(referral_id: str) -> str:
    """Sign a referral id into a URL-safe slip token."""
    return _slip_signer.dumps({"rid": str(referral_id)})


def decode_slip_token(token: str, max_age: int = SLIP_MAX_AGE_SECONDS) -> str | None:
    """Return the referral id from a slip token, or None if invalid/expired."""
    try:
        data = _slip_signer.loads(token, max_age=max_age)
    except SignatureExpired:
        logger.info("referral slip expired")
        return None
    except (BadSignature, Exception):
        return None
    rid = data.get("rid") if isinstance(data, dict) else None
    return str(rid) if rid else None


def _session(request: Request) -> dict:
    from src.presentation.opd.routes.opd_routes import _require_opd_session

    return _require_opd_session(request)


async def _my_clinic_id(sess: dict) -> str:
    from src.presentation.queue_engine.routes.queue_engine_routes import (
        _resolve_clinic_id,
    )

    return await _resolve_clinic_id(sess)


def _parse_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _urgency(value: Any) -> str:
    key = str(value or "").strip().upper()
    return key if key in VALID_URGENCIES else URGENCY_ROUTINE


# ── Create (sending clinic) ─────────────────────────────────────────────────


@router.post("/opd/api/referrals", include_in_schema=False)
async def create_referral(request: Request):
    """Send a patient from this clinic to another. Returns the signed slip URL.

    Body: ``{to_clinic_id, patient_id | (patient_name+phone), reason, note?,
    urgency?, source_token?}``
    """
    sess = _session(request)
    from_clinic_id = await _my_clinic_id(sess)

    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body or {}

    to_clinic_id = str(body.get("to_clinic_id") or "").strip()
    patient_id = str(body.get("patient_id") or "").strip()
    patient_name = str(body.get("patient_name") or "").strip()
    patient_phone = str(body.get("patient_phone") or "").strip()
    reason = str(body.get("reason") or "").strip()[:2000]
    note = str(body.get("note") or "").strip()[:2000]
    urgency = _urgency(body.get("urgency"))
    source_token_label = str(body.get("source_token") or "").strip()[:20]

    if not to_clinic_id:
        return JSONResponse(
            {"ok": False, "error": "Kis clinic ko bhej rahe hain — wo chunein."}, status_code=400
        )
    if not patient_id and not (patient_name and patient_phone):
        return JSONResponse(
            {
                "ok": False,
                "error": "Patient ka record chunein, ya naam + phone daalein.",
            },
            status_code=400,
        )
    if to_clinic_id == from_clinic_id:
        return JSONResponse(
            {"ok": False, "error": "Apni hi clinic ko referral nahi bhej sakte."},
            status_code=400,
        )

    to_uuid = _parse_uuid(to_clinic_id)
    if to_uuid is None:
        return JSONResponse({"ok": False, "error": "Clinic nahi mili."}, status_code=404)

    now = datetime.now(timezone.utc)
    referral_id = uuid.uuid4()

    async with async_session_factory() as session:
        target = await session.get(ClinicModel, to_uuid)
        if target is None or not target.is_active:
            return JSONResponse({"ok": False, "error": "Clinic nahi mili."}, status_code=404)

        # Fall back to the patient's own record for name/age/phone so the
        # receiving clinic sees a complete slip without the sender retyping it.
        patient_age = 0
        if patient_id:
            from src.infrastructure.patient.models.patient_model import PatientModel

            row = await session.execute(
                sa.select(PatientModel).where(PatientModel.patient_id == patient_id).limit(1)
            )
            found = row.scalars().first()
            if found is not None:
                patient_name = patient_name or (found.name or "")
                patient_phone = patient_phone or (found.phone or "")
                patient_age = int(found.age or 0)

        slip = make_slip_token(str(referral_id))
        session.add(
            ReferralModel(
                id=referral_id,
                from_clinic_id=from_clinic_id,
                from_doctor_id=str(sess.get("doctor_id") or "chief"),
                to_clinic_id=str(target.id),
                to_doctor_id="chief",
                patient_id=patient_id,
                patient_name=patient_name,
                patient_age=patient_age,
                patient_phone=patient_phone,
                reason=reason,
                note=note,
                urgency=urgency,
                source_token_label=source_token_label,
                status=STATUS_PENDING,
                slip_token=slip,
                expires_at=now + timedelta(days=SLIP_MAX_AGE_DAYS),
                is_open=True,
                created_by=str(sess.get("name") or "clinic"),
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
        target_name = target.clinic_name or ""

    from src.utils.public_url import public_base_url

    slip_url = f"{public_base_url(request)}/r/{slip}"
    return {
        "ok": True,
        "referral_id": str(referral_id),
        "to_clinic_name": target_name,
        "urgency": urgency,
        "urgency_label": URGENCY_LABEL.get(urgency, ""),
        "slip_url": slip_url,
        "expires_in_days": SLIP_MAX_AGE_DAYS,
        "message": (
            f"Referral slip ban gaya → {target_name}. "
            f"{URGENCY_LABEL.get(urgency, '')} priority. "
            "Ye link receiver ko WhatsApp par bhej dein."
        ),
    }


# ── Inbox (receiving clinic) ────────────────────────────────────────────────


@router.get("/opd/api/referrals", include_in_schema=False)
async def list_referrals(request: Request, include_closed: bool = Query(default=False)):
    """Referrals addressed to this clinic, most urgent first."""
    sess = _session(request)
    clinic_id = await _my_clinic_id(sess)

    async with async_session_factory() as session:
        stmt = sa.select(ReferralModel).where(ReferralModel.to_clinic_id == clinic_id)
        if not include_closed:
            stmt = stmt.where(ReferralModel.status == STATUS_PENDING)
        rows = list((await session.execute(stmt)).scalars().all())

        sender_ids = {str(r.from_clinic_id) for r in rows if r.from_clinic_id}
        names: dict[str, str] = {}
        if sender_ids:
            # Compare as real UUIDs, not cast strings: SQLite stores UUID
            # columns as 32-char hex without dashes, so a string ``IN`` list
            # silently matches nothing and every sender name comes back blank.
            sender_uuids = [
                parsed for parsed in (_parse_uuid(s) for s in sender_ids) if parsed
            ]
            if sender_uuids:
                sender_rows = await session.execute(
                    sa.select(ClinicModel.id, ClinicModel.clinic_name).where(
                        ClinicModel.id.in_(sender_uuids)
                    )
                )
                for cid, cname in sender_rows.all():
                    names[str(cid)] = cname or ""

    rows.sort(key=lambda r: (URGENCY_ORDER.get(r.urgency, 2), r.created_at or datetime.min))
    return {
        "ok": True,
        "clinic_id": clinic_id,
        "total": len(rows),
        "pending": sum(1 for r in rows if r.status == STATUS_PENDING),
        "referrals": [
            {
                "id": str(r.id),
                "from_clinic_name": names.get(str(r.from_clinic_id), ""),
                "from_doctor_id": r.from_doctor_id,
                "patient_name": r.patient_name,
                "patient_age": r.patient_age,
                "patient_id": r.patient_id,
                "reason": r.reason,
                "note": r.note,
                "urgency": r.urgency,
                "urgency_label": URGENCY_LABEL.get(r.urgency, ""),
                "source_token": r.source_token_label,
                "status": r.status,
                "slip_url": f"/r/{r.slip_token}" if r.slip_token else "",
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "accepted_token": r.accepted_token_label,
            }
            for r in rows
        ],
    }


# ── Public slip page ────────────────────────────────────────────────────────


async def _load_by_slip(session, token: str) -> ReferralModel | None:
    referral_id = decode_slip_token(token)
    if not referral_id:
        return None
    rid = _parse_uuid(referral_id)
    if rid is None:
        return None
    return await session.get(ReferralModel, rid)


@router.get("/r/{slip_token}", include_in_schema=False)
async def referral_slip_page(request: Request, slip_token: str):
    """Public slip page — what the receiving doctor opens from WhatsApp.

    Read-only: it shows the hand-off and offers an "Accept" button that calls
    the authenticated endpoint. Opening the link itself changes nothing except
    a view counter, so a forwarded slip cannot move a patient's queue position.
    """
    async with async_session_factory() as session:
        referral = await _load_by_slip(session, slip_token)
        if referral is None:
            return HTMLResponse(_slip_error("Ye referral link galat ya expire ho gaya hai."), status_code=404)

        from_name = to_name = ""
        for cid, attr in ((referral.from_clinic_id, "from"), (referral.to_clinic_id, "to")):
            uuid_value = _parse_uuid(cid)
            if uuid_value is None:
                continue
            clinic = await session.get(ClinicModel, uuid_value)
            label = (clinic.clinic_name or "") if clinic else ""
            if attr == "from":
                from_name = label
            else:
                to_name = label

        referral.viewed_count = int(referral.viewed_count or 0) + 1
        referral.viewed_at = datetime.now(timezone.utc)
        await session.commit()

        data = {
            "patient_name": referral.patient_name or "—",
            "patient_age": referral.patient_age,
            "patient_phone": referral.patient_phone or "",
            "patient_id": referral.patient_id or "",
            "reason": referral.reason or "",
            "note": referral.note or "",
            "urgency": referral.urgency,
            "urgency_label": URGENCY_LABEL.get(referral.urgency, ""),
            "status": referral.status,
            "source_token": referral.source_token_label,
            "created_at": referral.created_at.isoformat() if referral.created_at else "",
            "expires_at": referral.expires_at.isoformat() if referral.expires_at else "",
        }

    import jinja2

    loader = jinja2.FileSystemLoader(str(_TEMPLATES_DIR))
    env = jinja2.Environment(loader=loader, auto_reload=True)
    html = env.get_template("referral_slip.html").render(
        slip_token=slip_token,
        # The id is behind the signed token already, so exposing it lets the
        # Accept button act without a second lookup race.
        referral_id=str(referral.id),
        from_clinic=from_name,
        to_clinic=to_name,
        **data,
    )
    return HTMLResponse(content=html)


def _slip_error(message: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Referral — GIL Clinic</title>
<style>
 body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        background:#f1f5f9; display:flex; align-items:center; justify-content:center;
        min-height:100vh; margin:0; padding:20px; }}
 .box {{ background:#fff; border-radius:16px; padding:34px; text-align:center;
         max-width:420px; box-shadow:0 12px 40px rgba(15,23,42,.1); }}
 .big {{ font-size:40px; margin-bottom:10px; }}
 h1 {{ font-size:18px; color:#0f172a; margin-bottom:8px; }}
 p {{ color:#64748b; font-size:14px; line-height:1.6; }}
</style></head><body>
<div class="box"><div class="big">🔗</div>
<h1>Referral link kaam nahi kar raha</h1><p>{message}</p></div>
</body></html>"""


# ── Accept / decline (receiving clinic, authenticated) ──────────────────────


@router.post("/opd/api/referrals/{referral_id}/accept", include_in_schema=False)
async def accept_referral(request: Request, referral_id: str):
    """Accept a referral → create a REAL token in the receiving clinic's queue.

    This is the only path that puts a referred patient into a queue, and it
    requires this clinic's own session. The referral is marked accepted before
    the queue entry is written, so a retry cannot create a second token.
    """
    sess = _session(request)
    clinic_id = await _my_clinic_id(sess)

    rid = _parse_uuid(referral_id)
    if rid is None:
        return JSONResponse({"ok": False, "error": "Referral nahi mila."}, status_code=404)

    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body or {}
    # Reception may want the patient seen now rather than at the back.
    at_front = bool(body.get("at_front"))

    now = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        referral = await session.get(ReferralModel, rid)
        if referral is None:
            return JSONResponse({"ok": False, "error": "Referral nahi mila."}, status_code=404)

        # Tenancy: only the addressed clinic may accept.
        if str(referral.to_clinic_id) != str(clinic_id):
            return JSONResponse(
                {"ok": False, "error": "Ye referral aapki clinic ke liye nahi hai."},
                status_code=403,
            )
        if referral.status == STATUS_ACCEPTED:
            return JSONResponse(
                {
                    "ok": False,
                    "error": (
                        f"Ye referral pehle hi accept ho chuka hai "
                        f"(token {referral.accepted_token_label or '—'})."
                    ),
                },
                status_code=409,
            )
        if referral.status in (STATUS_DECLINED, STATUS_CANCELLED):
            return JSONResponse(
                {"ok": False, "error": f"Ye referral {referral.status} hai."},
                status_code=400,
            )
        if not referral.is_open:
            return JSONResponse(
                {"ok": False, "error": "Ye slip band ho chuki hai."}, status_code=400
            )
        expiry = referral.expires_at
        if expiry is not None:
            aware = expiry if expiry.tzinfo else expiry.replace(tzinfo=timezone.utc)
            if aware < now:
                return JSONResponse(
                    {"ok": False, "error": "Ye referral expire ho gaya — naya banayein."},
                    status_code=400,
                )

        from src.presentation.queue_engine.routes.queue_engine_routes import (
            _active_entries,
            _clinic_specialty,
        )
        from src.shared.domain.base_entity import uuid7

        doctor_id = str(sess.get("doctor_id") or "chief")
        date_prefix = now.strftime("%Y%m%d")

        # Next routine token, partitioned per clinic + doctor + day.
        token_row = await session.execute(
            sa.select(sa.func.coalesce(sa.func.max(QueueEntryModel.token_number), 0)).where(
                QueueEntryModel.clinic_id == str(clinic_id),
                QueueEntryModel.doctor_id == doctor_id,
                QueueEntryModel.service_code == "OPD",
                QueueEntryModel.visit_type != "emergency",
                QueueEntryModel.visit_id.like(f"VIS-{date_prefix}-%"),
            )
        )
        token = int(token_row.scalar() or 0) + 1

        # Where to place them: the back of the line by default — a referral is
        # a real patient but not an emergency, and jumping the queue would be
        # unfair to everyone already waiting.
        siblings = await _active_entries(session, str(clinic_id), doctor_id)
        waiting_keys = [
            float(e.sort_key if e.sort_key is not None else (e.token_number or 0))
            for e in siblings
            if (e.status or "").upper() in ("WAITING", "CALLED", "HOLD")
        ]
        if at_front and waiting_keys:
            new_key = min(waiting_keys) - 0.5
            position_note = "Reception ne front par lagaya."
        else:
            new_key = (max(waiting_keys) + 1.0) if waiting_keys else float(token)
            position_note = "Line ke aakhir me — baaki waiting patients ka haq safe."

        # Reuse the patient's existing record when the referral carries one.
        patient_uuid = str(uuid7())
        patient_key = referral.patient_id or f"REF-{date_prefix}-{token:03d}"
        patient_name = referral.patient_name or "Referred patient"
        if referral.patient_id:
            from src.infrastructure.patient.models.patient_model import PatientModel

            row = await session.execute(
                sa.select(PatientModel)
                .where(PatientModel.patient_id == referral.patient_id)
                .limit(1)
            )
            found = row.scalars().first()
            if found is not None:
                patient_uuid = str(found.id)
                patient_name = found.name or patient_name

        visit_type = ewt.classify_visit_type(
            total_visits=None,
            has_report=bool(referral.reason),
        )
        entry = QueueEntryModel(
            id=uuid7(),
            clinic_id=str(clinic_id),
            doctor_id=doctor_id,
            visit_id=f"VIS-{date_prefix}-{uuid7().hex[:6]}",
            patient_id=patient_key,
            patient_uuid=patient_uuid,
            patient_name=patient_name,
            service_code="OPD",
            token_number=token,
            department="OPD",
            room="OPD Room",
            status="WAITING",
            priority=1 if referral.urgency == URGENCY_URGENT else 0,
            display_order=0,
            sort_key=float(new_key),
            visit_type=visit_type,
            complexity_weight=ewt.complexity_weight(visit_type),
            notes=(f"{TAG_REFERRAL_NOTE}: {referral.reason or ''}").strip()[:2000],
            created_by="referral",
            updated_by="referral",
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(entry)

        referral.status = STATUS_ACCEPTED
        referral.accepted_at = now
        referral.accepted_entry_id = str(entry.id)
        referral.is_open = False
        referral.updated_at = now

        specialty = await _clinic_specialty(session, str(clinic_id))
        label = token_label.token_label(token, token_label.specialty_prefix(specialty))
        referral.accepted_token_label = label

        # ``accepted_token_label`` is written before commit, so a retry sees
        # status=ACCEPTED and is refused above rather than minting a second token.
        await session.flush()
        entries_now = len(siblings) + 1
        await session.commit()

    return {
        "ok": True,
        "token": token,
        "token_label": label,
        "patient_name": referral.patient_name,
        "position_note": position_note,
        "patients_in_queue": entries_now,
        "message": (
            f"Referral accept — {label} ({referral.patient_name}) aapki queue me. "
            f"{position_note}"
        ),
    }


@router.post("/opd/api/referrals/{referral_id}/decline", include_in_schema=False)
async def decline_referral(request: Request, referral_id: str):
    """Decline a referral. Nothing enters the queue, and the sender can be told why."""
    sess = _session(request)
    clinic_id = await _my_clinic_id(sess)

    rid = _parse_uuid(referral_id)
    if rid is None:
        return JSONResponse({"ok": False, "error": "Referral nahi mila."}, status_code=404)

    try:
        body = await request.json()
    except Exception:
        body = {}
    reason = str((body or {}).get("reason") or "").strip()[:200]

    async with async_session_factory() as session:
        referral = await session.get(ReferralModel, rid)
        if referral is None:
            return JSONResponse({"ok": False, "error": "Referral nahi mila."}, status_code=404)
        if str(referral.to_clinic_id) != str(clinic_id):
            return JSONResponse(
                {"ok": False, "error": "Ye referral aapki clinic ke liye nahi hai."},
                status_code=403,
            )
        if referral.status != STATUS_PENDING:
            return JSONResponse(
                {"ok": False, "error": f"Ye referral pehle hi {referral.status} hai."},
                status_code=400,
            )
        referral.status = STATUS_DECLINED
        referral.declined_reason = reason
        referral.is_open = False
        referral.updated_at = datetime.now(timezone.utc)
        await session.commit()

    return {
        "ok": True,
        "message": (
            "Referral decline kar diya. "
            + (f"Reason: {reason}" if reason else "Sender ko bata dijiye taaki wo doosra centre dekh sake.")
        ),
    }
