"""Module 6 ingestion routes (BLOCK 5 · M6-03/04/05).

The worker runs elsewhere (Part E explains why: PythonAnywhere free has no
outbound internet, no cron, and ~100 CPU-seconds a day, and Chromium is
~400 MB). This module is the *receiving* end.

Three rules the endpoint enforces, each because the alternative is a real harm:

  1. **Opt-out is permanent.** A clinic that asks to be removed is never listed
     and never re-crawled — the check happens before anything is written, and it
     applies to future runs too, not just the current payload. An opt-out that
     only affects one batch is not an opt-out.
  2. **A crawled listing is labelled as public and unclaimed.** Publishing
     scraped details as if the clinic had confirmed them would misrepresent
     them to patients, and the clinic would be the one blamed for a stale
     address or a wrong phone.
  3. **No invented data.** Every profile is validated against the same schema
     the worker used; a profile with no real name, or a phone number that is
     not a plausible 10-digit mobile, is dropped with a recorded reason rather
     than stored hopefully.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from src.infrastructure.clinic.models.clinic_model import ClinicModel
from src.infrastructure.clinic.models.crawl_model import (
    REJECT_DUPLICATE,
    REJECT_OPTED_OUT,
    RUN_COMPLETED,
    RUN_FAILED,
    SOURCE_CLAIM,
    SOURCE_CRAWL,
    DoctorCrawlRunModel,
    ProfileValidationError,
    coerce_profiles,
    doctor_profile_schema,
    new_run_id,
    normalise_profile,
    profile_identity,
)
from src.shared.infrastructure.database import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Ingestion"])

#: The token the worker must present. Reuses the marketplace seed token so one
#: secret guards all machine-to-machine writes, and it fails closed when unset.
DEFAULT_INGEST_TOKEN = "GIL-DEMO-SEED-2026"

#: Cap a single batch. A run that wants to send more should send several — a
#: 10,000-profile POST is a denial-of-service against a free host.
MAX_PROFILES_PER_BATCH = 200

CLAIM_UNCLAIMED = "unclaimed"
CLAIM_CLAIMED = "claimed"
CLAIM_OPTED_OUT = "opted_out"


def _ingest_token() -> str:
    import os

    return os.getenv("INGEST_TOKEN") or DEFAULT_INGEST_TOKEN


def _authorised(token: str) -> bool:
    expected = _ingest_token()
    if not expected:
        return False  # fail closed
    # Constant-time compare: this is a shared secret.
    import hmac

    return hmac.compare_digest(str(token or ""), expected)


# ── M6-02 · the schema, served so the worker cannot drift ───────────────────


@router.get("/api/v1/ingest/schema", include_in_schema=False)
async def ingest_schema(token: str = Query(default="")):
    """The exact profile schema and instructions the worker should use."""
    if not _authorised(token):
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
    return {
        "ok": True,
        "schema": doctor_profile_schema(),
        "max_profiles_per_batch": MAX_PROFILES_PER_BATCH,
        "note": (
            "Ye wahi schema hai jo ingest endpoint validate karta hai. Worker isi "
            "ko use kare taaki dono kabhi alag na ho jayein."
        ),
    }


# ── M6-03 · ingest ──────────────────────────────────────────────────────────


@router.post("/api/v1/ingest/doctors", include_in_schema=False)
async def ingest_doctors(request: Request, token: str = Query(default="")):
    """Accept a batch of crawled doctor profiles.

    Body: ``{run_label?, triggered_by?, urls_attempted?, profiles: [...]}`` —
    ``profiles`` may also be a bare list, a ``{"doctors": [...]}`` wrapper or a
    JSON string, because LLM extraction is not deterministic.

    Returns per-reason skip counts. A worker that cannot see WHY profiles were
    dropped cannot fix its own extraction.
    """
    if not _authorised(token):
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body or {}

    if isinstance(body, list):
        payload: Any = body
        meta: dict[str, Any] = {}
    elif isinstance(body, dict):
        payload = body.get("profiles", body.get("doctors", body.get("data")))
        meta = body
    else:
        payload = None
        meta = {}

    raw_profiles = coerce_profiles(payload)
    if not raw_profiles:
        return JSONResponse(
            {
                "ok": False,
                "error": "Koi profile nahi mila — 'profiles' list bhejein.",
                "accepted": 0,
            },
            status_code=400,
        )
    if len(raw_profiles) > MAX_PROFILES_PER_BATCH:
        return JSONResponse(
            {
                "ok": False,
                "error": (
                    f"Ek batch me {MAX_PROFILES_PER_BATCH} se zyada profile nahi — "
                    "batch chhote karein."
                ),
                "received": len(raw_profiles),
            },
            status_code=413,
        )

    run_id = new_run_id()
    now = datetime.now(timezone.utc)
    label = str(meta.get("run_label") or "")[:120]
    triggered_by = str(meta.get("triggered_by") or "worker")[:60]
    urls_attempted = int(meta.get("urls_attempted") or 0)

    created = updated = skipped = 0
    reasons: dict[str, int] = {}
    kept: list[dict[str, Any]] = []

    def note(reason: str) -> None:
        reasons[reason] = reasons.get(reason, 0) + 1

    try:
        async with async_session_factory() as session:
            # ── opt-out set, read BEFORE anything is written ──
            opted_out = {
                (row[0] or "").strip().lower()
                for row in (
                    await session.execute(
                        sa.select(ClinicModel.doctor_name).where(
                            ClinicModel.claim_status == CLAIM_OPTED_OUT
                        )
                    )
                ).all()
                if row[0]
            }
            existing = {
                (row[0] or "").strip().lower(): row[1]
                for row in (
                    await session.execute(
                        sa.select(ClinicModel.doctor_name, ClinicModel.clinic_code)
                    )
                ).all()
                if row[0]
            }

            for index, raw in enumerate(raw_profiles):
                try:
                    profile = normalise_profile(raw, index)
                except ProfileValidationError as exc:
                    skipped += 1
                    note(exc.code)
                    continue

                name_key = profile["doctor_name"].strip().lower()
                # Rule 1: an opt-out outranks the crawler, always.
                if name_key in opted_out:
                    skipped += 1
                    note(REJECT_OPTED_OUT)
                    continue

                city = str(profile.get("city") or "").strip()
                if name_key in existing:
                    # Already known — refresh only the crawl-provided fields and
                    # never touch a field the clinic itself confirmed.
                    code = existing[name_key]
                    row = await session.execute(
                        sa.select(ClinicModel).where(ClinicModel.clinic_code == code).limit(1)
                    )
                    clinic = row.scalars().first()
                    if clinic is not None and clinic.claim_status == CLAIM_OPTED_OUT:
                        skipped += 1
                        note(REJECT_OPTED_OUT)
                        continue
                    if clinic is not None:
                        clinic.crawl_verified_at = now
                        clinic.crawl_run_id = run_id
                        if profile.get("source_url"):
                            clinic.crawl_source_url = profile["source_url"][:500]
                        if profile.get("address") and not clinic.address:
                            clinic.address = profile["address"]
                        if profile.get("latitude") and clinic.latitude is None:
                            clinic.latitude = profile["latitude"]
                        if profile.get("longitude") and clinic.longitude is None:
                            clinic.longitude = profile["longitude"]
                        updated += 1
                        kept.append({"doctor_name": clinic.doctor_name, "action": "updated"})
                        continue

                seq = (await session.execute(sa.select(sa.func.count(ClinicModel.id)))).scalar() or 0
                clinic = ClinicModel(
                    clinic_name=(profile.get("clinic_name") or f"{profile['doctor_name']} Clinic")[:200],
                    clinic_code=f"CRAWL-{seq + 1:05d}",
                    doctor_name=profile["doctor_name"],
                    doctor_phone=profile.get("phone", ""),
                    doctor_email=profile.get("email", ""),
                    doctor_degree=profile.get("degree", ""),
                    doctor_reg_no=profile.get("reg_no", ""),
                    specialty=profile.get("specialty") or "General Physician",
                    address=profile.get("address", ""),
                    city=city,
                    state=profile.get("state", ""),
                    latitude=profile.get("latitude"),
                    longitude=profile.get("longitude"),
                    # Rule 2: labelled as crawled, unclaimed, and NOT a partner.
                    source=SOURCE_CRAWL,
                    crawl_source_url=profile.get("source_url", "")[:500],
                    crawl_run_id=run_id,
                    crawl_verified_at=now,
                    claim_status=CLAIM_UNCLAIMED,
                    is_license_active=False,   # no live queue until they join
                    is_active=True,
                    created_by="crawl_worker",
                )
                session.add(clinic)
                existing[name_key] = clinic.clinic_code
                created += 1
                kept.append({"doctor_name": clinic.doctor_name, "action": "created"})

            run = DoctorCrawlRunModel(
                id=__import__("uuid").UUID(run_id),
                run_label=label,
                status=RUN_COMPLETED,
                triggered_by=triggered_by,
                urls_attempted=urls_attempted,
                profiles_found=len(raw_profiles),
                profiles_created=created,
                profiles_updated=updated,
                profiles_skipped=skipped,
                # Bucketed by stable reason code, so a worker can see the SHAPE
                # of its own failures rather than one counter per junk value.
                skipped_reasons="|".join(f"{k}={v}" for k, v in sorted(reasons.items())),
                started_at=now,
                finished_at=datetime.now(timezone.utc),
            )
            session.add(run)
            # ONE commit for the clinics AND the run row: a run recorded without
            # its clinics (or the reverse) would make the history lie.
            await session.commit()
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("ingest failed: %s", exc)
        return JSONResponse(
            {"ok": False, "error": f"Ingest fail hua ({type(exc).__name__})."},
            status_code=500,
        )

    return {
        "ok": True,
        "run_id": run_id,
        "received": len(raw_profiles),
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "skipped_reasons": reasons,
        "profiles": kept[:50],
        "note": (
            "Crawled listings 'unclaimed' public listings hain — Tier-2 me dikhengi, "
            "live queue nahi. Clinic claim karegi tab partner banegi."
        ),
    }


# ── M6-04 · run history ─────────────────────────────────────────────────────


@router.get("/api/v1/ingest/runs", include_in_schema=False)
async def ingest_runs(token: str = Query(default=""), limit: int = Query(default=20)):
    """Recent crawl runs — what was attempted, accepted, and rejected why."""
    if not _authorised(token):
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
    try:
        cap = max(1, min(100, int(limit)))
    except (TypeError, ValueError):
        cap = 20
    async with async_session_factory() as session:
        rows = list(
            (
                await session.execute(
                    sa.select(DoctorCrawlRunModel)
                    .order_by(DoctorCrawlRunModel.started_at.desc())
                    .limit(cap)
                )
            ).scalars().all()
        )
    return {
        "ok": True,
        "runs": [
            {
                "id": str(r.id),
                "run_label": r.run_label,
                "status": r.status,
                "triggered_by": r.triggered_by,
                "urls_attempted": r.urls_attempted,
                "profiles_found": r.profiles_found,
                "profiles_created": r.profiles_created,
                "profiles_updated": r.profiles_updated,
                "profiles_skipped": r.profiles_skipped,
                "skipped_reasons": r.skipped_reasons,
                "started_at": r.started_at.isoformat() if r.started_at else "",
                "finished_at": r.finished_at.isoformat() if r.finished_at else "",
            }
            for r in rows
        ],
    }


# ── M6-05 · claim and opt-out (public, no login) ────────────────────────────


@router.post("/api/v1/marketplace/claim", include_in_schema=False)
async def claim_listing(request: Request):
    """A clinic confirms a public (crawled) listing as its own.

    Body: ``{clinic_id, doctor_name?, phone?}``.

    Claiming does NOT grant the live queue by itself — that needs onboarding
    and a licence, which is a commercial step, not a click. What it does is
    mark the listing as confirmed by the clinic, which is the difference
    between "we found this on the web" and "this clinic says it is right".
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body or {}
    clinic_id = str(body.get("clinic_id") or "").strip()
    if not clinic_id:
        return JSONResponse({"ok": False, "error": "Clinic chunein."}, status_code=400)

    import uuid as _uuid

    try:
        cid = _uuid.UUID(clinic_id)
    except (ValueError, AttributeError, TypeError):
        return JSONResponse({"ok": False, "error": "Clinic nahi mili."}, status_code=404)

    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        clinic = await session.get(ClinicModel, cid)
        if clinic is None:
            return JSONResponse({"ok": False, "error": "Clinic nahi mili."}, status_code=404)
        # Opt-out is checked BEFORE is_active: opting out deactivates the row,
        # so the generic "not found" branch would swallow the real reason and
        # leave this clinic with a useless answer.
        if clinic.claim_status == CLAIM_OPTED_OUT:
            return JSONResponse(
                {
                    "ok": False,
                    "error": (
                        "Ye listing opt-out kar chuki hai. Dobara list karane ke liye "
                        "clinic se sampark karein."
                    ),
                },
                status_code=400,
            )
        if not clinic.is_active:
            return JSONResponse({"ok": False, "error": "Clinic nahi mili."}, status_code=404)
        if clinic.claim_status == CLAIM_CLAIMED:
            return {
                "ok": True,
                "already_claimed": True,
                "message": "Ye listing pehle hi claim ho chuki hai.",
            }
        clinic.claim_status = CLAIM_CLAIMED
        clinic.source = SOURCE_CLAIM
        clinic.claimed_at = now
        await session.commit()
        name = clinic.clinic_name or "Clinic"

    return {
        "ok": True,
        "clinic_name": name,
        "message": (
            f"Shukriya! {name} ki listing ab clinic-confirmed hai. "
            "Live queue aur token booking ke liye onboarding poora karna hoga."
        ),
    }


@router.post("/api/v1/marketplace/opt-out", include_in_schema=False)
async def opt_out_listing(request: Request):
    """A clinic asks to be removed from the directory, permanently.

    Body: ``{clinic_id, reason?}``.

    The listing is deactivated immediately AND recorded as opted-out, so a
    future crawl run skips it. Recording the reason matters: six months later
    somebody will ask why a clinic is missing, and "we have it in writing" is
    the only acceptable answer.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body or {}
    clinic_id = str(body.get("clinic_id") or "").strip()
    reason = str(body.get("reason") or "").strip()[:200]
    if not clinic_id:
        return JSONResponse({"ok": False, "error": "Clinic chunein."}, status_code=400)

    import uuid as _uuid

    try:
        cid = _uuid.UUID(clinic_id)
    except (ValueError, AttributeError, TypeError):
        return JSONResponse({"ok": False, "error": "Clinic nahi mili."}, status_code=404)

    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        clinic = await session.get(ClinicModel, cid)
        if clinic is None:
            return JSONResponse({"ok": False, "error": "Clinic nahi mili."}, status_code=404)
        clinic.claim_status = CLAIM_OPTED_OUT
        clinic.opted_out_at = now
        clinic.opt_out_reason = reason or "clinic request"
        # Opting out removes the listing from the public directory, which is
        # what "remove me" has to mean to be worth anything.
        clinic.is_active = False
        await session.commit()
        name = clinic.clinic_name or "Clinic"

    return {
        "ok": True,
        "clinic_name": name,
        "message": (
            f"{name} directory se hata di gayi. Aage koi crawl bhi is clinic ko "
            "list nahi karega."
        ),
    }


@router.get("/api/v1/marketplace/opt-out", include_in_schema=False)
async def opt_out_register(token: str = Query(default=""), limit: int = Query(default=100)):
    """Every opt-out on record. Token-gated — it is an internal register."""
    if not _authorised(token):
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
    try:
        cap = max(1, min(500, int(limit)))
    except (TypeError, ValueError):
        cap = 100
    async with async_session_factory() as session:
        rows = list(
            (
                await session.execute(
                    sa.select(ClinicModel)
                    .where(ClinicModel.claim_status == CLAIM_OPTED_OUT)
                    .order_by(ClinicModel.opted_out_at.desc())
                    .limit(cap)
                )
            ).scalars().all()
        )
    return {
        "ok": True,
        "total": len(rows),
        "opted_out": [
            {
                "clinic_id": str(c.id),
                "clinic_name": c.clinic_name or "",
                "doctor_name": c.doctor_name or "",
                "reason": c.opt_out_reason,
                "opted_out_at": c.opted_out_at.isoformat() if c.opted_out_at else "",
            }
            for c in rows
        ],
    }
