"""External lab network — order → result → patient phone (GAP-09).

DOCTOR (opd_session):
    POST /opd/api/lab-order              → naya lab order (patient result link)
    GET  /opd/api/lab-orders             → orders list (?patient_id=)
    POST /opd/api/lab-order/{id}/send    → "external lab ko bhejo" (stub)
    POST /opd/api/lab-result             → result submit (order reported)

PUBLIC (token = secret):
    GET  /lab/{token}                    → patient ke phone par result view

External lab ka real API partner ke saath aayega — abhi lifecycle LOCAL me
fully working hai (external call stubbed, crash nahi hota).
"""

from __future__ import annotations

import json
import logging
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jinja2
import sqlalchemy as sa
from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from src.infrastructure.lab.models import LabOrderModel
from src.infrastructure.patient.models.patient_model import PatientModel
from src.shared.infrastructure.database import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Lab Network"])
doctor_router = APIRouter(prefix="/opd/api", tags=["Lab Network (Doctor)"])

_TEMPLATES_DIR = Path(__file__).parents[4] / "templates"
_jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)), auto_reload=True)
_jinja_env.cache = {}


def _render(name: str, **context: Any) -> str:
    return _jinja_env.get_template(name).render(**context)


def _new_token() -> str:
    return secrets.token_urlsafe(16)


@doctor_router.post("/lab-order", include_in_schema=False)
async def create_lab_order(request: Request):
    """Doctor naya lab order banata hai — patient ko result link milta hai."""
    from src.presentation.opd.routes.opd_routes import _require_opd_session  # lazy

    sess = _require_opd_session(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    patient_id = str(body.get("patient_id") or "").strip()
    tests = str(body.get("tests") or "").strip()
    if not patient_id or not tests:
        return JSONResponse({"ok": False, "error": "patient_id aur tests chahiye"}, status_code=400)

    async with async_session_factory() as session:
        patient = None
        prow = await session.execute(
            sa.select(PatientModel).where(PatientModel.patient_id == patient_id).limit(1)
        )
        patient = prow.scalar_one_or_none()
        order = LabOrderModel(
            clinic_id=sess.get("clinic_id") or None,
            doctor_id=sess.get("doctor_id") or "chief",
            patient_id=patient_id,
            patient_name=body.get("patient_name") or (patient.name if patient else ""),
            phone=body.get("phone") or (patient.phone if patient else ""),
            tests=tests,
            sample_type=str(body.get("sample_type") or "blood"),
            priority=str(body.get("priority") or "routine"),
            external_lab=str(body.get("external_lab") or ""),
            status="ordered",
            report_token=_new_token(),
        )
        session.add(order)
        await session.commit()
        order_id = str(order.id)
        token = order.report_token

    from src.utils.public_url import public_base_url

    result_url = f"{public_base_url(request)}/lab/{token}"
    return JSONResponse(
        {
            "ok": True,
            "order_id": order_id,
            "report_token": token,
            "result_url": result_url,
            "message": f"Lab order ban gaya. Result aane par patient is link se dekhega: {result_url}",
        }
    )


@doctor_router.get("/lab-orders", include_in_schema=False)
async def list_lab_orders(request: Request, patient_id: str = Query("")):
    """Doctor ke liye orders list (patient filter ke saath)."""
    from src.presentation.opd.routes.opd_routes import _require_opd_session  # lazy

    _require_opd_session(request)
    async with async_session_factory() as session:
        stmt = sa.select(LabOrderModel).order_by(LabOrderModel.created_at.desc()).limit(100)
        if patient_id.strip():
            stmt = sa.select(LabOrderModel).where(LabOrderModel.patient_id == patient_id.strip()).order_by(LabOrderModel.created_at.desc()).limit(100)
        rows = (await session.execute(stmt)).scalars().all()
        out = [
            {
                "id": str(o.id), "patient_id": o.patient_id, "patient_name": o.patient_name,
                "tests": o.tests, "status": o.status, "priority": o.priority,
                "external_lab": o.external_lab, "report_token": o.report_token,
                "reported_at": o.reported_at.isoformat() if o.reported_at else "",
            }
            for o in rows
        ]
    return {"ok": True, "orders": out, "count": len(out)}


@doctor_router.post("/lab-order/{order_id}/send", include_in_schema=False)
async def send_lab_order(request: Request, order_id: str):
    """External lab ko order bhejo — abhi stub (real lab API partner ke saath)."""
    from src.presentation.opd.routes.opd_routes import _require_opd_session  # lazy

    _require_opd_session(request)
    try:
        oid = uuid.UUID(order_id)
    except (ValueError, AttributeError, TypeError):
        return JSONResponse({"ok": False, "error": "Invalid order id"}, status_code=400)
    async with async_session_factory() as session:
        order = await session.get(LabOrderModel, oid)
        if order is None:
            return JSONResponse({"ok": False, "error": "Order nahi mila"}, status_code=404)
        order.status = "sent"
        order.external_order_ref = "LAB-" + secrets.token_hex(4).upper()
        await session.commit()
        ref = order.external_order_ref
    return JSONResponse(
        {
            "ok": True,
            "status": "sent",
            "external_order_ref": ref,
            "note": "External lab API stub — real partner lab connect hone par yahan HTTP call hoga.",
        }
    )


@doctor_router.post("/lab-result", include_in_schema=False)
async def submit_lab_result(request: Request):
    """Lab result submit — order reported + patient result view live.

    Body: {order_id, results: [{test, value, unit, ref_range, flag}]}
    """
    from src.presentation.opd.routes.opd_routes import _require_opd_session  # lazy

    _require_opd_session(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    order_id = str(body.get("order_id") or "").strip()
    results = body.get("results") or []
    if not order_id or not isinstance(results, list) or not results:
        return JSONResponse({"ok": False, "error": "order_id aur results chahiye"}, status_code=400)
    try:
        oid = uuid.UUID(order_id)
    except (ValueError, AttributeError, TypeError):
        return JSONResponse({"ok": False, "error": "Invalid order id"}, status_code=400)

    async with async_session_factory() as session:
        order = await session.get(LabOrderModel, oid)
        if order is None:
            return JSONResponse({"ok": False, "error": "Order nahi mila"}, status_code=404)
        order.result_json = json.dumps(results, default=str)
        order.status = "reported"
        order.reported_at = datetime.now(timezone.utc)
        await session.commit()
        token = order.report_token

    return JSONResponse(
        {"ok": True, "status": "reported", "result_url": f"/lab/{token}", "reported": len(results)}
    )


@router.get("/lab/{token}", include_in_schema=False)
async def lab_result_page(request: Request, token: str):
    """Patient ke phone par result view (read-only, token = secret)."""
    async with async_session_factory() as session:
        row = await session.execute(
            sa.select(LabOrderModel).where(LabOrderModel.report_token == token)
        )
        order = row.scalar_one_or_none()
    if order is None:
        return HTMLResponse(
            _render("lab_result.html", found=False, patient_name="", tests="", results=[],
                    status="", reported_at="", order_id=""),
            status_code=404,
        )
    try:
        results = json.loads(order.result_json or "[]")
    except Exception:
        results = []
    return HTMLResponse(
        _render(
            "lab_result.html",
            found=True,
            patient_name=order.patient_name or "Patient",
            tests=[t.strip() for t in (order.tests or "").splitlines() if t.strip()],
            results=results,
            status=order.status,
            reported_at=order.reported_at.strftime("%d %b %Y, %I:%M %p") if order.reported_at else "",
            order_id=str(order.id),
        )
    )
