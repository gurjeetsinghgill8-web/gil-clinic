"""
Patient Portal routes (Smart OPD) — patient khud apni readings bhare aur kisi bhi
doctor ko read-only link bhej sake.

PUBLIC (login nahi, token = secret)
  GET    /my/{token}                     → patient portal page (entry + trends + table)
  POST   /my/{token}/verify              → registered mobile verify (session cookie)
  GET    /my/{token}/data                → readings JSON
  POST   /my/{token}/readings            → readings save
  DELETE /my/{token}/readings/{rid}      → apni galti se bhari reading delete
  GET    /my/{token}/content             → trends + table + flags ka HTML fragment
  GET    /my/{token}/chart.svg?code=...  → ek metric ka trend graph (SVG)
  GET    /my/{token}/export?fmt=pdf|html|csv
  POST   /my/{token}/share               → read-only doctor link banao / refresh karo
  GET    /s/{token}                      → doctor ke liye READ-ONLY record
  GET    /s/{token}/export?fmt=...

DOCTOR (opd_session cookie)
  POST   /opd/api/patient-link           → patient ka portal link + WhatsApp text
  GET    /opd/api/patient-readings       → patient ke self-readings + series
  GET    /opd/api/patient-report         → wahi report doctor download kare
  GET    /opd/api/portal-stats           → chhote numbers (kitne link, kitni readings)

⚠️ `/s/` par **koi write endpoint nahi** hai — jaan-boojh kar. Doctor sirf dekh sakta hai.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jinja2
import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from src.infrastructure.opd.models.patient_portal_models import (
    PatientPortalLinkModel,
    PatientReadingModel,
    PatientShareModel,
)
from src.infrastructure.patient.models.patient_model import PatientModel
from src.shared.infrastructure.database import async_session_factory
from src.utils import patient_tokens as tk
from src.utils.patient_chart_svg import trend_chart_svg, trend_point_count
from src.utils.patient_metrics import (
    FORM_CODES,
    METRICS,
    build_series,
    flag_reading,
    format_dt,
    guidance_for,
    latest_reading_by_key,
    metric_by_code,
    normal_range_text,
    pivot_readings,
    reading_public,
    worst_of,
)
from src.utils.patient_portal_html import flags_html, summary_html, table_html, trends_html
from src.utils.patient_report import build_report_csv, build_report_html, build_report_pdf

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Patient Portal"])
doctor_router = APIRouter(prefix="/opd/api", tags=["Patient Portal (Doctor)"])

DEFAULT_CLINIC = "GIL CLINIC"
MAX_READINGS_PER_REPORT = 1000

# ── Jinja2 (same pattern as opd_routes / main_v2) ────────────────────────────
_TEMPLATES_DIR = Path(__file__).parents[4] / "templates"
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)), auto_reload=True
)
_jinja_env.cache = {}


def _render(name: str, **context: Any) -> str:
    return _jinja_env.get_template(name).render(**context)


def _base_url(request: Request) -> str:
    """Public base URL — APP_BASE_URL zinda ho to wahi, warna request ka host.

    (`.env` me purana tunnel/Railway URL pada ho to patient ka link toota hua na
    jaye — `src/utils/public_url.py` dekhein.)
    """
    from src.utils.public_url import public_base_url

    return public_base_url(request)


def _error_page(title: str, message: str, status_code: int = 400) -> HTMLResponse:
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>body{{font-family:system-ui,'Segoe UI',Roboto,Arial,sans-serif;background:#f1f5f9;margin:0;
display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}}
.card{{background:#fff;border-radius:14px;padding:26px 22px;max-width:430px;text-align:center;
box-shadow:0 4px 18px rgba(15,23,42,.08)}}
h1{{font-size:19px;margin:8px 0 6px}}p{{color:#475569;font-size:14px;line-height:1.6;margin:6px 0}}
.icon{{font-size:44px}}</style></head>
<body><div class="card"><div class="icon">🔗</div><h1>{title}</h1><p>{message}</p></div></body></html>"""
    return HTMLResponse(content=html, status_code=status_code)


# ── DB helpers ───────────────────────────────────────────────────────────────
async def _portal_link(session, token: str) -> Optional[PatientPortalLinkModel]:
    row = await session.execute(
        sa.select(PatientPortalLinkModel).where(PatientPortalLinkModel.token == token)
    )
    link = row.scalar_one_or_none()
    if link is None or not link.active:
        return None
    if tk.is_expired(link.expires_at):
        return None
    return link


async def _share(session, token: str) -> Optional[PatientShareModel]:
    row = await session.execute(
        sa.select(PatientShareModel).where(PatientShareModel.token == token)
    )
    share = row.scalar_one_or_none()
    if share is None or tk.is_expired(share.expires_at):
        return None
    return share


async def _readings(session, patient_id: str, limit: int = 500) -> List[Dict[str, Any]]:
    rows = await session.execute(
        sa.select(PatientReadingModel)
        .where(PatientReadingModel.patient_id == patient_id)
        .order_by(PatientReadingModel.date_time.desc())
        .limit(limit)
    )
    return [r.to_dict() for r in rows.scalars()]


async def _patient(session, patient_id: str) -> Optional[PatientModel]:
    row = await session.execute(
        sa.select(PatientModel).where(PatientModel.patient_id == patient_id).limit(1)
    )
    return row.scalar_one_or_none()


def _flags(readings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Latest reading per metric jo normal nahi hai (red-flag banner ke liye)."""
    out: List[Dict[str, Any]] = []
    for key, r in latest_reading_by_key(readings).items():
        if (r.get("status") or "ok") == "ok":
            continue
        out.append(
            {
                "label": r.get("label") or key,
                "value": r.get("value"),
                "unit": r.get("unit") or "",
                "status": r.get("status"),
                "guidance": guidance_for(metric_by_code(r.get("code") or ""), r.get("status")),
            }
        )
    return out


def _verified(request: Request, token: str) -> bool:
    return tk.read_patient_session(request.cookies.get(tk.PATIENT_SESSION_COOKIE_PREFIX + token), token)


def _portal_payload(link: PatientPortalLinkModel, readings: List[Dict[str, Any]]) -> Dict[str, Any]:
    series = build_series(readings)
    return {
        "ok": True,
        "patient_id": link.patient_id,
        "patient_name": link.patient_name or "Patient",
        "readings": readings,
        "series": series,
        "flags": _flags(readings),
    }


def _report_ctx(
    patient_name: str,
    patient_id: str,
    readings: List[Dict[str, Any]],
    *,
    clinic_name: str = DEFAULT_CLINIC,
    mode: str = "patient",
    note: str = "",
    valid_till: str = "",
) -> Dict[str, Any]:
    return {
        "clinic_name": clinic_name,
        "patient_name": patient_name,
        "patient_id": patient_id,
        "readings": readings[:MAX_READINGS_PER_REPORT],
        "mode": mode,
        "note": note,
        "valid_till": valid_till,
    }


def _download(ctx: Dict[str, Any], fmt: str) -> Response:
    """Report file (PDF / HTML / CSV) — teeno me graphs aate hain."""
    fmt = (fmt or "pdf").lower()
    stamp = _dt.date.today().isoformat()
    safe_id = "".join(ch for ch in (ctx["patient_id"] or "patient") if ch.isalnum() or ch in "-_")
    prefix = "shared" if ctx.get("mode") == "shared" else "patient"
    filename = f"{prefix}-{safe_id}-records-{stamp}"
    if fmt == "html":
        return Response(
            content=build_report_html(ctx),
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}.html"'},
        )
    if fmt == "csv":
        return Response(
            content=build_report_csv(ctx["readings"]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )
    pdf = build_report_pdf(ctx)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}.pdf"'},
    )


# ── brute-force guard (verify screen) ────────────────────────────────────────
_verify_attempts: Dict[str, List[float]] = {}
MAX_VERIFY_ATTEMPTS = 6
VERIFY_WINDOW_SEC = 600


def _too_many_attempts(token: str) -> bool:
    now = time.time()
    hits = [t for t in _verify_attempts.get(token, []) if now - t < VERIFY_WINDOW_SEC]
    _verify_attempts[token] = hits
    return len(hits) >= MAX_VERIFY_ATTEMPTS


def _note_attempt(token: str) -> None:
    _verify_attempts.setdefault(token, []).append(time.time())


# ═════════════════════════════════════════════════════════════════════════════
# PATIENT PORTAL (public — token = secret)
# ═════════════════════════════════════════════════════════════════════════════
@router.get("/my/{token}", include_in_schema=False)
async def patient_portal_page(request: Request, token: str):
    async with async_session_factory() as session:
        link = await _portal_link(session, token)
        if link is None:
            return _error_page(
                "Ye link kaam nahi kar raha",
                "Link adhoora, purana ya doctor ne band kar diya ho sakta hai. "
                "Kripya clinic se naya link maangein.",
                404,
            )
        verified = _verified(request, token)
        readings = await _readings(session, link.patient_id) if verified else []
        link.use_count = (link.use_count or 0) + 1
        link.last_used_at = tk.now_utc()
        await session.commit()

    series = build_series(readings)
    pivot = pivot_readings(readings)
    form_metrics = [
        {"code": m.code, "label": m.label, "unit": m.unit} for m in METRICS if m.code in FORM_CODES
    ]
    return HTMLResponse(
        _render(
            "patient_portal.html",
            clinic_name=DEFAULT_CLINIC,
            token=token,
            verified=verified,
            patient_name=link.patient_name or "Patient",
            patient_id=link.patient_id,
            phone_last4=link.phone_last4 or "",
            form_metrics=form_metrics,
            readings_count=len(readings),
            trends=trends_html(series),
            table=table_html(pivot),
            flags=flags_html(_flags(readings)),
            summary=summary_html(readings),
            share_days=tk.SHARE_DAYS_DEFAULT,
        )
    )


@router.post("/my/{token}/verify", include_in_schema=False)
async def patient_portal_verify(request: Request, token: str):
    """Registered mobile ka last-10 digit match — phir 12 ghante ka session cookie."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    phone = str((body or {}).get("phone") or "")
    if _too_many_attempts(token):
        return JSONResponse(
            {"ok": False, "error": "Bahut baar galat number dala gaya — 10 minute baad koshish karein."},
            status_code=429,
        )
    async with async_session_factory() as session:
        link = await _portal_link(session, token)
        if link is None:
            return JSONResponse({"ok": False, "error": "Link kaam nahi kar raha"}, status_code=404)
        patient = await _patient(session, link.patient_id)
        stored_phone = (patient.phone if patient else "") or link.phone or ""
        stored_hash = (patient.phone_hash if patient else "") or ""
        if not tk.phone_matches(phone, stored_phone, stored_hash):
            _note_attempt(token)
            return JSONResponse(
                {
                    "ok": False,
                    "error": "Number match nahi hua. Kripya wahi 10-digit number dalein jo clinic me darj hai"
                    + (f" (•••• {link.phone_last4})" if link.phone_last4 else ""),
                },
                status_code=403,
            )
    resp = JSONResponse({"ok": True})
    resp.set_cookie(
        tk.PATIENT_SESSION_COOKIE_PREFIX + token,
        tk.make_patient_session(token),
        max_age=tk.PATIENT_SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return resp


@router.get("/my/{token}/data", include_in_schema=False)
async def patient_portal_data(request: Request, token: str):
    if not _verified(request, token):
        return JSONResponse({"ok": False, "error": "verify required"}, status_code=401)
    async with async_session_factory() as session:
        link = await _portal_link(session, token)
        if link is None:
            return JSONResponse({"ok": False, "error": "Link kaam nahi kar raha"}, status_code=404)
        readings = await _readings(session, link.patient_id)
    return JSONResponse(_portal_payload(link, readings))


@router.get("/my/{token}/content", include_in_schema=False)
async def patient_portal_content(request: Request, token: str):
    """Save ke baad JS isse trends + table + flags fresh karta hai (page reload nahi)."""
    if not _verified(request, token):
        return JSONResponse({"ok": False, "error": "verify required"}, status_code=401)
    async with async_session_factory() as session:
        link = await _portal_link(session, token)
        if link is None:
            return JSONResponse({"ok": False, "error": "Link kaam nahi kar raha"}, status_code=404)
        readings = await _readings(session, link.patient_id)
    series = build_series(readings)
    return JSONResponse(
        {
            "ok": True,
            "count": len(readings),
            "trends": trends_html(series),
            "table": table_html(pivot_readings(readings)),
            "flags": flags_html(_flags(readings)),
            "summary": summary_html(readings),
        }
    )


@router.post("/my/{token}/readings", include_in_schema=False)
async def patient_portal_save(request: Request, token: str):
    """Readings save — body: {dateTime, values:[{code,value,label?,unit?}]}"""
    if not _verified(request, token):
        return JSONResponse({"ok": False, "error": "Pehle mobile number verify karein"}, status_code=401)
    try:
        body = await request.json()
    except Exception:
        body = {}
    date_time = str((body or {}).get("dateTime") or "").strip() or tk.now_utc().isoformat()
    values = (body or {}).get("values") or []
    if not isinstance(values, list) or not values:
        return JSONResponse({"ok": False, "error": "Koi value nahi mili"}, status_code=400)

    saved: List[Dict[str, Any]] = []
    async with async_session_factory() as session:
        link = await _portal_link(session, token)
        if link is None:
            return JSONResponse({"ok": False, "error": "Link kaam nahi kar raha"}, status_code=404)
        for item in values[:30]:
            try:
                value = float((item or {}).get("value"))
            except (TypeError, ValueError):
                continue
            code = str((item or {}).get("code") or "custom").strip() or "custom"
            metric = metric_by_code(code)
            label = str((item or {}).get("label") or (metric.label if metric else code)).strip()
            unit = str((item or {}).get("unit") or (metric.unit if metric else "")).strip()
            if code == "custom":
                code = "custom"
                if not label:
                    continue
            row = PatientReadingModel(
                patient_id=link.patient_id,
                code=code,
                label=label or code,
                unit=unit,
                value=value,
                date_time=date_time,
                source="patient",
                status=flag_reading(metric, value),
                note=str((item or {}).get("note") or ""),
            )
            session.add(row)
            saved.append(
                {
                    "code": code,
                    "label": row.label,
                    "unit": unit,
                    "value": value,
                    "status": row.status,
                }
            )
        if not saved:
            return JSONResponse({"ok": False, "error": "Koi valid value nahi mili"}, status_code=400)
        await session.commit()
        readings = await _readings(session, link.patient_id)

    series = build_series(readings)
    return JSONResponse(
        {
            "ok": True,
            "saved": saved,
            "count": len(readings),
            "trends": trends_html(series),
            "table": table_html(pivot_readings(readings)),
            "flags": flags_html(_flags(readings)),
            "summary": summary_html(readings),
            "alerts": [s for s in saved if (s.get("status") or "ok") != "ok"],
            "alerts_text": [
                guidance_for(metric_by_code(s["code"]), s["status"])
                for s in saved
                if (s.get("status") or "ok") != "ok"
            ],
        }
    )


@router.delete("/my/{token}/readings/{reading_id}", include_in_schema=False)
async def patient_portal_delete(request: Request, token: str, reading_id: str):
    """Patient apni galti se bhari reading delete kar sakta hai (sirf apni)."""
    if not _verified(request, token):
        return JSONResponse({"ok": False, "error": "verify required"}, status_code=401)
    try:
        rid = uuid.UUID(str(reading_id))
    except (ValueError, AttributeError, TypeError):
        return JSONResponse({"ok": False, "error": "Reading nahi mili"}, status_code=404)
    async with async_session_factory() as session:
        link = await _portal_link(session, token)
        if link is None:
            return JSONResponse({"ok": False, "error": "Link kaam nahi kar raha"}, status_code=404)
        row = await session.execute(
            sa.select(PatientReadingModel).where(PatientReadingModel.id == rid)
        )
        reading = row.scalar_one_or_none()
        if reading is None or reading.patient_id != link.patient_id:
            return JSONResponse({"ok": False, "error": "Reading nahi mili"}, status_code=404)
        await session.delete(reading)
        await session.commit()
        readings = await _readings(session, link.patient_id)
    series = build_series(readings)
    return JSONResponse(
        {
            "ok": True,
            "count": len(readings),
            "trends": trends_html(series),
            "table": table_html(pivot_readings(readings)),
            "flags": flags_html(_flags(readings)),
            "summary": summary_html(readings),
        }
    )


@router.get("/my/{token}/chart.svg", include_in_schema=False)
async def patient_portal_chart(request: Request, token: str, code: str = Query(...), w: int = 320, h: int = 160):
    """Ek metric ka trend graph — screen aur file dono me YAHI SVG use hota hai."""
    async with async_session_factory() as session:
        link = await _portal_link(session, token)
        if link is None:
            return Response(content="", media_type="image/svg+xml", status_code=404)
        readings = await _readings(session, link.patient_id)
    for s in build_series(readings):
        if s["code"] == code:
            svg = trend_chart_svg(
                s["values"],
                s["dates"],
                unit=s["unit"],
                normal_min=s.get("normal_min"),
                normal_max=s.get("normal_max"),
                width=max(200, min(900, int(w))),
                height=max(100, min(500, int(h))),
            )
            return Response(content=svg or "", media_type="image/svg+xml")
    return Response(content="", media_type="image/svg+xml", status_code=404)


@router.get("/my/{token}/export", include_in_schema=False)
async def patient_portal_export(request: Request, token: str, fmt: str = Query("pdf")):
    """Poora record download — PDF / HTML (inline graphs) / CSV (Excel)."""
    if not _verified(request, token):
        return _error_page("Download ke liye verify karein", "Pehle apna registered mobile number dalein.", 401)
    async with async_session_factory() as session:
        link = await _portal_link(session, token)
        if link is None:
            return _error_page("Link kaam nahi kar raha", "Clinic se naya link maangein.", 404)
        readings = await _readings(session, link.patient_id, MAX_READINGS_PER_REPORT)
    return _download(_report_ctx(link.patient_name or "Patient", link.patient_id, readings), fmt)


@router.post("/my/{token}/share", include_in_schema=False)
async def patient_portal_share(request: Request, token: str):
    """Read-only 'Doctor ko bhejo' link — snapshot + 7 din expiry."""
    if not _verified(request, token):
        return JSONResponse({"ok": False, "error": "Pehle mobile number verify karein"}, status_code=401)
    try:
        body = await request.json()
    except Exception:
        body = {}
    note = str((body or {}).get("note") or "").strip()[:600]
    days = int((body or {}).get("days") or tk.SHARE_DAYS_DEFAULT)
    reuse = bool((body or {}).get("reuse"))

    async with async_session_factory() as session:
        link = await _portal_link(session, token)
        if link is None:
            return JSONResponse({"ok": False, "error": "Link kaam nahi kar raha"}, status_code=404)
        readings = await _readings(session, link.patient_id, MAX_READINGS_PER_REPORT)

        share: Optional[PatientShareModel] = None
        if reuse:
            row = await session.execute(
                sa.select(PatientShareModel)
                .where(PatientShareModel.patient_id == link.patient_id)
                .order_by(PatientShareModel.created_at.desc())
                .limit(1)
            )
            candidate = row.scalar_one_or_none()
            if candidate is not None:
                share = candidate
        if share is None:
            share = PatientShareModel(token=tk.new_token(24), patient_id=link.patient_id)
            session.add(share)

        payload = {
            "patient_name": link.patient_name or "Patient",
            "patient_id": link.patient_id,
            "readings": readings,
            "clinic_name": DEFAULT_CLINIC,
            "created_at": tk.now_utc().isoformat(),
        }
        share.patient_name = link.patient_name or "Patient"
        share.note = note
        share.payload_json = json.dumps(payload, default=str)
        share.expires_at = tk.share_expiry(days)
        await session.commit()
        share_token = share.token
        expires_at = share.expires_at

    url = f"{_base_url(request)}/s/{share_token}"
    message = (
        f"Namaste Doctor, ye mera health record hai (self-monitoring — BP, sugar, pulse, weight). "
        f"Link kholiye — poora record aur graphs dikh jayenge. Ye read-only hai:\n{url}"
    )
    if note:
        message += f"\n\nMera sandesh: {note}"
    return JSONResponse(
        {
            "ok": True,
            "url": url,
            "token": share_token,
            "expires_at": expires_at.isoformat() if expires_at else "",
            "expires_text": format_dt(expires_at) if expires_at else "",
            "whatsapp_url": "https://wa.me/?text=" + _quote(message),
            "message": message,
        }
    )


# ═════════════════════════════════════════════════════════════════════════════
# READ-ONLY SHARE VIEW (koi bhi doctor — app/PIN/login nahi)
# ═════════════════════════════════════════════════════════════════════════════
@router.get("/s/{token}", include_in_schema=False)
async def shared_record_page(request: Request, token: str):
    async with async_session_factory() as session:
        share = await _share(session, token)
        if share is None:
            return _error_page(
                "Ye link ki samay-seema khatam ho gayi",
                "Suraksha ke liye share link 7 din baad apne aap band ho jata hai. "
                "Patient se naya link maangein.",
                410,
            )
        share.view_count = (share.view_count or 0) + 1
        await session.commit()
        payload = {}
        try:
            payload = json.loads(share.payload_json or "{}")
        except Exception:
            payload = {}
        readings = payload.get("readings") or []
        patient_name = share.patient_name or payload.get("patient_name") or "Patient"
        patient_id = share.patient_id or payload.get("patient_id") or ""
        note = share.note or ""
        expires_at = share.expires_at

    series = build_series(readings)
    return HTMLResponse(
        _render(
            "patient_shared.html",
            clinic_name=payload.get("clinic_name") or DEFAULT_CLINIC,
            token=token,
            patient_name=patient_name,
            patient_id=patient_id,
            readings_count=len(readings),
            trends=trends_html(series),
            table=table_html(pivot_readings(readings)),
            flags=flags_html(_flags(readings)),
            summary=summary_html(readings),
            note=note,
            valid_till=format_dt(expires_at) if expires_at else "",
            created_at=format_dt(payload.get("created_at") or ""),
        )
    )


@router.get("/s/{token}/export", include_in_schema=False)
async def shared_record_export(request: Request, token: str, fmt: str = Query("pdf")):
    async with async_session_factory() as session:
        share = await _share(session, token)
        if share is None:
            return _error_page("Link expire ho gaya", "Patient se naya link maangein.", 410)
        payload = {}
        try:
            payload = json.loads(share.payload_json or "{}")
        except Exception:
            payload = {}
    ctx = _report_ctx(
        share.patient_name or "Patient",
        share.patient_id,
        payload.get("readings") or [],
        clinic_name=payload.get("clinic_name") or DEFAULT_CLINIC,
        mode="shared",
        note=share.note or "",
        valid_till=format_dt(share.expires_at) if share.expires_at else "",
    )
    return _download(ctx, fmt)


# ═════════════════════════════════════════════════════════════════════════════
# DOCTOR SIDE (opd_session cookie) — link banao, readings dekho, report lo
# ═════════════════════════════════════════════════════════════════════════════
def _require_doctor(request: Request) -> Dict[str, Any]:
    from src.presentation.opd.routes.opd_routes import _require_opd_session  # lazy (no import cycle)

    return _require_opd_session(request)


async def _clinic_name(doctor_id: str) -> str:
    try:
        from src.presentation.opd.routes.opd_routes import _get_settings  # lazy

        settings = await _get_settings(doctor_id, masked=True)
        return (settings or {}).get("clinic_name") or DEFAULT_CLINIC
    except Exception:
        return DEFAULT_CLINIC


@doctor_router.post("/patient-link", include_in_schema=False)
async def api_patient_link(request: Request):
    """Patient ka portal link banao (ya maujooda wapas do) + WhatsApp text."""
    sess = _require_doctor(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    patient_id = str((body or {}).get("patient_id") or "").strip()
    patient_name = str((body or {}).get("patient_name") or "").strip()
    phone = str((body or {}).get("phone") or "").strip()
    if not patient_id and not phone:
        return JSONResponse({"ok": False, "error": "patient_id ya phone chahiye"}, status_code=400)

    async with async_session_factory() as session:
        if not patient_id and phone:
            found = await session.execute(
                sa.select(PatientModel)
                .where(PatientModel.phone_hash == tk.phone_hash(phone))
                .limit(1)
            )
            p = found.scalar_one_or_none()
            if p is None:
                found = await session.execute(
                    sa.select(PatientModel)
                    .where(PatientModel.phone == tk.normalize_phone(phone))
                    .limit(1)
                )
                p = found.scalar_one_or_none()
            if p is not None:
                patient_id = p.patient_id
                patient_name = patient_name or p.name
                phone = phone or p.phone
        if not patient_id:
            return JSONResponse(
                {"ok": False, "error": "Is number se patient record nahi mila — pehle patient register karein"},
                status_code=404,
            )

        patient = await _patient(session, patient_id)
        if patient is not None:
            patient_name = patient_name or patient.name
            phone = phone or patient.phone

        row = await session.execute(
            sa.select(PatientPortalLinkModel)
            .where(
                PatientPortalLinkModel.patient_id == patient_id,
                PatientPortalLinkModel.active == 1,
            )
            .order_by(PatientPortalLinkModel.created_at.desc())
            .limit(1)
        )
        link = row.scalar_one_or_none()
        if link is None or tk.is_expired(link.expires_at):
            link = PatientPortalLinkModel(
                token=tk.new_token(24),
                patient_id=patient_id,
                patient_name=patient_name or "Patient",
                phone=tk.normalize_phone(phone),
                phone_last4=tk.phone_last4(phone),
                created_by=sess.get("doctor_id") or "",
                expires_at=tk.portal_expiry(),
            )
            session.add(link)
        else:
            link.patient_name = patient_name or link.patient_name
            if phone:
                link.phone = tk.normalize_phone(phone)
                link.phone_last4 = tk.phone_last4(phone)
        await session.commit()
        token = link.token
        readings_count = len(await _readings(session, patient_id, 1000))

    url = f"{_base_url(request)}/my/{token}"
    first_name = (patient_name or "ji").split(" ")[0]
    message = (
        f"Namaste {first_name} ji, ab aap ghar baithe apni BP, sugar, pulse, weight ki reading "
        f"khud bhar sakte hain — clinic aane ki zarurat nahi.\n\n"
        f"Ye aapka personal link hai (kisi aur ko na dein):\n{url}\n\n"
        f"Kholne par apna 10-digit mobile number dalein. Reading bharne ke baad aap apna graph "
        f"dekh sakte hain aur zarurat pade to PDF download karke kisi bhi doctor ko dikha sakte hain."
    )
    wa_target = "https://wa.me/?text="
    digits = tk.normalize_phone(phone)
    if len(digits) == 10:
        wa_target = f"https://wa.me/91{digits}?text="
    return JSONResponse(
        {
            "ok": True,
            "url": url,
            "token": token,
            "patient_id": patient_id,
            "patient_name": patient_name or "Patient",
            "readings_count": readings_count,
            "message": message,
            "whatsapp_url": wa_target + _quote(message),
            "phone": digits if len(digits) == 10 else "",
        }
    )


@doctor_router.get("/patient-readings", include_in_schema=False)
async def api_patient_readings(request: Request, patient_id: str = Query(...)):
    """Doctor ke Patient Monitor tab ke liye — readings + series + flags + ready HTML.

    `trends`/`table` HTML bhi bhejte hain taaki dashboard me **chart code dobara na
    likhna pade** — wahi server-rendered SVG fragment jo patient ko dikhta hai.
    """
    _require_doctor(request)
    async with async_session_factory() as session:
        patient = await _patient(session, patient_id)
        readings = await _readings(session, patient_id)
        name = patient.name if patient is not None else patient_id
        phone = patient.phone if patient is not None else ""
    series = build_series(readings)
    flags = _flags(readings)
    return JSONResponse(
        {
            "ok": True,
            "patient_id": patient_id,
            "patient_name": name,
            "phone": phone or "",
            "readings": readings,
            "series": series,
            "flags": flags,
            "count": len(readings),
            "trends": trends_html(series),
            "table": table_html(pivot_readings(readings)),
            "flags_html": flags_html(flags),
        }
    )


@doctor_router.get("/patient-report", include_in_schema=False)
async def api_patient_report(
    request: Request, patient_id: str = Query(...), fmt: str = Query("pdf")
):
    """Doctor bhi wahi report download kare (patient ko milne wali file)."""
    sess = _require_doctor(request)
    async with async_session_factory() as session:
        patient = await _patient(session, patient_id)
        readings = await _readings(session, patient_id, MAX_READINGS_PER_REPORT)
    clinic = await _clinic_name(sess.get("doctor_id") or "")
    ctx = _report_ctx(
        patient.name if patient is not None else patient_id,
        patient_id,
        readings,
        clinic_name=clinic,
    )
    return _download(ctx, fmt)


@doctor_router.get("/portal-patients", include_in_schema=False)
async def api_portal_patients(request: Request, q: str = Query("")):
    """Patient Monitor tab ki list — jin patients ne ghar se readings bhari hain."""
    _require_doctor(request)
    q = (q or "").strip()
    async with async_session_factory() as session:
        ids: Optional[List[str]] = None
        if q:
            like = f"%{q}%"
            found = await session.execute(
                sa.select(PatientModel.patient_id)
                .where(
                    sa.or_(
                        PatientModel.name.ilike(like),
                        PatientModel.phone.ilike(like),
                        PatientModel.patient_id.ilike(like),
                    )
                )
                .limit(25)
            )
            ids = [r[0] for r in found.all()]
            if not ids:
                return JSONResponse({"ok": True, "patients": [], "count": 0})

        base = sa.select(
            PatientReadingModel.patient_id,
            sa.func.count(PatientReadingModel.id).label("cnt"),
            sa.func.max(PatientReadingModel.date_time).label("last_at"),
        )
        if ids is not None:
            base = base.where(PatientReadingModel.patient_id.in_(ids))
        grouped = await session.execute(
            base.group_by(PatientReadingModel.patient_id).order_by(sa.desc("last_at")).limit(60)
        )
        rows = grouped.all()
        patient_ids = [r[0] for r in rows]
        if not patient_ids:
            return JSONResponse({"ok": True, "patients": [], "count": 0})

        names: Dict[str, str] = {}
        phones: Dict[str, str] = {}
        pres = await session.execute(
            sa.select(PatientModel).where(PatientModel.patient_id.in_(patient_ids))
        )
        for p in pres.scalars():
            names[p.patient_id] = p.name
            phones[p.patient_id] = p.phone or ""

        links = await session.execute(
            sa.select(PatientPortalLinkModel).where(
                PatientPortalLinkModel.patient_id.in_(patient_ids),
                PatientPortalLinkModel.active == 1,
            )
        )
        has_link = {row.patient_id for row in links.scalars()}

        # har patient ki latest reading (label/value/unit/status)
        latest: Dict[str, Dict[str, Any]] = {}
        lres = await session.execute(
            sa.select(PatientReadingModel)
            .where(PatientReadingModel.patient_id.in_(patient_ids))
            .order_by(PatientReadingModel.date_time.desc())
        )
        for r in lres.scalars():
            if r.patient_id not in latest:
                latest[r.patient_id] = r.to_dict()

    patients = []
    for pid, cnt, last_at in rows:
        lr = latest.get(pid) or {}
        patients.append(
            {
                "patient_id": pid,
                "patient_name": names.get(pid) or pid,
                "phone": phones.get(pid) or "",
                "count": int(cnt or 0),
                "last_at": last_at or "",
                "last_at_text": format_dt(last_at) if last_at else "",
                "last_label": lr.get("label") or "",
                "last_value": lr.get("value"),
                "last_unit": lr.get("unit") or "",
                "last_status": lr.get("status") or "ok",
                "has_link": pid in has_link,
            }
        )
    return JSONResponse({"ok": True, "patients": patients, "count": len(patients)})


@doctor_router.get("/base-url", include_in_schema=False)
async def api_base_url(request: Request):
    """Patient links kis base URL se ban rahe hain + wo zinda hai ya nahi."""
    _require_doctor(request)
    from src.utils.public_url import base_url_status

    return JSONResponse({"ok": True, **base_url_status(request)})


@doctor_router.get("/portal-stats", include_in_schema=False)
async def api_portal_stats(request: Request):
    """Chhote numbers: kitne portal link ban chuke, kitni self-readings aayi."""
    _require_doctor(request)
    async with async_session_factory() as session:
        links = await session.execute(sa.select(sa.func.count()).select_from(PatientPortalLinkModel))
        active = await session.execute(
            sa.select(sa.func.count())
            .select_from(PatientPortalLinkModel)
            .where(PatientPortalLinkModel.active == 1)
        )
        readings = await session.execute(sa.select(sa.func.count()).select_from(PatientReadingModel))
        shares = await session.execute(sa.select(sa.func.count()).select_from(PatientShareModel))
        patients = await session.execute(
            sa.select(sa.func.count(sa.distinct(PatientReadingModel.patient_id)))
        )
    from src.utils.public_url import base_url_status

    return JSONResponse(
        {
            "ok": True,
            "links_total": int(links.scalar() or 0),
            "links_active": int(active.scalar() or 0),
            "readings_total": int(readings.scalar() or 0),
            "shares_total": int(shares.scalar() or 0),
            "patients_with_readings": int(patients.scalar() or 0),
            "link_health": base_url_status(request),
        }
    )


def _quote(text: str) -> str:
    from urllib.parse import quote

    return quote(text, safe="")
