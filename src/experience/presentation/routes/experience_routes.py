"""Experience Engine — FastAPI routes.

Patient-facing API for the PWA experience.
All endpoints are stateless — they read from other engines, never own data.

API Contract:
    POST   /api/v1/experience/login           — Phone/QR/ID → session token
    GET    /api/v1/experience/me               — Current patient info
    GET    /api/v1/experience/my-status          — Live test statuses + ETA
    GET    /api/v1/experience/token-slip        — Printable token slip HTML
    POST   /api/v1/experience/inquiry           — Send "Ask Reception"
    GET    /api/v1/experience/inquiry           — Get current inquiry
    DELETE /api/v1/experience/inquiry           — Clear inquiry (staff)
    POST   /api/v1/experience/feedback          — Submit patient feedback
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from fastapi.responses import HTMLResponse

from src.application.common.command import Command, Query as CQRSQuery
from src.experience.application.use_cases import (
    PatientLoginUseCase,
    PatientStatusUseCase,
    PatientTimelineUseCase,
    TokenSlipUseCase,
    PatientInquiryUseCase,
    FeedbackUseCase,
    refresh_session,
)
from src.experience.presentation.schemas.experience_schemas import (
    PhoneLoginRequest,
    QRLoginRequest,
    PatientIdLoginRequest,
    LoginResponse,
    StatusResponse,
    TokenSlipResponse,
    InquirySendRequest,
    InquiryResponse,
    FeedbackRequest,
    FeedbackResponse,
    ErrorResponse,
)
from src.experience.presentation.dependencies.experience_dependencies import (
    get_login_use_case,
    get_status_use_case,
    get_token_slip_use_case,
    get_inquiry_use_case,
    get_patient_alert_use_case,
    get_feedback_use_case,
    get_timeline_use_case,
    require_patient_session,
)
from src.presentation.queue.dependencies.queue_dependencies import get_queue_repo
from src.infrastructure.clinic.settings_provider import get_clinic_settings

from pathlib import Path
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

PWA_DIR = Path(__file__).parent.parent.parent / "pwa"

router = APIRouter(tags=["experience"])
api_router = APIRouter(prefix="/api/v1/experience", tags=["experience-api"])


# =============================================================================
# Login
# =============================================================================


@api_router.post(
    "/login",
    response_model=LoginResponse,
    summary="Patient login via phone, QR, or patient ID",
)
async def login(
    request: Request,
    use_case: PatientLoginUseCase = Depends(get_login_use_case),
):
    """Authenticate a patient.

    Supports three methods:
    - phone: POST {"method": "phone", "phone": "9876543210"}
    - qr:    POST {"method": "qr", "qr_payload": "<encrypted_payload>"}
    - patient_id: POST {"method": "patient_id", "patient_id": "CQ-20260714-001"}

    Returns a session_token for subsequent /me and /my-status calls.
    """
    body = await request.json()
    method = body.get("method", "phone")

    command = Command(data=body)
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.error,
        )

    return result.data


# =============================================================================
# Current Patient
# =============================================================================


@api_router.get(
    "/me",
    summary="Get current patient info",
)
async def get_current_patient(
    session: dict = Depends(require_patient_session),
):
    """Return basic info about the currently logged-in patient."""
    return {
        "patient_id": session["patient_id"],
        "phone_hash": session["phone_hash"][:12] + "...",
        "session_created_at": session["created_at"].isoformat(),
        "session_expires_at": session["expires_at"].isoformat(),
    }


# =============================================================================
# Live Status
# =============================================================================


@api_router.get(
    "/my-status",
    response_model=StatusResponse,
    summary="Get live patient status and test queue info",
)
async def get_my_status(
    session: dict = Depends(require_patient_session),
    use_case: PatientStatusUseCase = Depends(get_status_use_case),
):
    """Get the patient's current status including test queue positions,
    estimated wait times, and expected completion times."""
    # Refresh session
    refresh_session_from_header(None, session)

    cqrs_query = CQRSQuery(data={
        "patient_uuid": session["patient_uuid"],
    })
    result = await use_case.run(cqrs_query)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error,
        )

    return result.data


# =============================================================================
# Token Slip
# =============================================================================


@api_router.get(
    "/token-slip",
    response_class=HTMLResponse,
    summary="Get printable token slip",
)
async def get_token_slip(
    session: dict = Depends(require_patient_session),
    use_case: TokenSlipUseCase = Depends(get_token_slip_use_case),
):
    """Generate a printable token slip with patient info and QR code.

    Returns raw HTML that can be printed directly or displayed in an iframe.
    """
    command = Command(data={
        "patient_uuid": session["patient_uuid"],
        "tests": [],  # Will be populated from Queue Engine when ready
    })
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error,
        )

    return HTMLResponse(content=result.data["html"])


@api_router.get(
    "/token-slip/json",
    response_model=TokenSlipResponse,
    summary="Get token slip data as JSON",
)
async def get_token_slip_json(
    session: dict = Depends(require_patient_session),
    use_case: TokenSlipUseCase = Depends(get_token_slip_use_case),
):
    """Get token slip data as JSON (for mobile apps or custom rendering)."""
    command = Command(data={
        "patient_uuid": session["patient_uuid"],
        "tests": [],
    })
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error,
        )

    return result.data


# =============================================================================
# Inquiry (Ask Reception)
# =============================================================================


@api_router.post(
    "/inquiry",
    response_model=InquiryResponse,
    summary="Send a message to reception",
)
async def send_inquiry(
    request: InquirySendRequest,
    session: dict = Depends(require_patient_session),
    use_case: PatientInquiryUseCase = Depends(get_inquiry_use_case),
):
    """Send an inquiry to the reception desk.

    The patient's message appears on the reception dashboard.
    """
    command = Command(data={
        "operation": "send",
        "patient_uuid": session["patient_uuid"],
        "inquiry_text": request.inquiry_text,
    })
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    return result.data


@api_router.get(
    "/inquiry",
    response_model=InquiryResponse,
    summary="Check current inquiry status",
)
async def get_inquiry(
    session: dict = Depends(require_patient_session),
    use_case: PatientInquiryUseCase = Depends(get_inquiry_use_case),
):
    """Check if there is an active inquiry and see its current status."""
    command = Command(data={
        "operation": "get",
        "patient_uuid": session["patient_uuid"],
    })
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error,
        )

    return result.data


@api_router.delete(
    "/inquiry",
    response_model=InquiryResponse,
    summary="Clear inquiry (staff)",
)
async def clear_inquiry(
    session: dict = Depends(require_patient_session),
    use_case: PatientInquiryUseCase = Depends(get_inquiry_use_case),
):
    """Clear the current inquiry (after staff has responded)."""
    command = Command(data={
        "operation": "clear",
        "patient_uuid": session["patient_uuid"],
    })
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error,
        )

    return result.data


# =============================================================================
# Helpers
# =============================================================================


def refresh_session_from_header(
    authorization: str | None, session: dict
) -> None:
    """Extend the session TTL on each request.

    Called automatically by authenticated endpoints.
    """
    refresh_session(session.get("_token", ""))


# =============================================================================
# Alert Status — Patient checks for pending alerts
# =============================================================================


@api_router.get(
    "/alert-status",
    summary="Check for pending alert (beep + vibrate trigger)",
)
async def check_alert_status(
    session: dict = Depends(require_patient_session),
    use_case=Depends(get_patient_alert_use_case),
):
    """Check if there is a pending alert from the technician.

    Returns:
        {"alert": true, "message": "...", "room": "..."} if alert pending.
        The alert is auto-cleared after being read.

    The PWA client should call this on every refresh cycle and
    trigger browser beep + vibration + banner if alert is true.
    """
    refresh_session_from_header(None, session)

    command = Command(data={
        "patient_uuid": session["patient_uuid"],
    })
    result = await use_case.run(command)

    if result.is_fail:
        return {
            "alert": False,
            "message": None,
        }

    return result.data


# =============================================================================
# Patient Timeline — Full journey history
# =============================================================================


@api_router.get(
    "/my-timeline",
    summary="Get patient's full journey timeline",
)
async def get_my_timeline(
    session: dict = Depends(require_patient_session),
    use_case: PatientTimelineUseCase = Depends(get_timeline_use_case),
):
    """Get the patient's complete journey timeline.

    Returns all events (registered → called → started → completed →
    report_ready → delivered) grouped by visit, sorted chronologically.
    """
    refresh_session_from_header(None, session)

    command = Command(data={
        "patient_uuid": session["patient_uuid"],
    })
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error,
        )

    return result.data


# =============================================================================
# Report Detail — Patient views a specific report
# =============================================================================


@api_router.get(
    "/report/{entry_id}",
    summary="Get detailed report info for a queue entry",
)
async def get_report_detail(
    entry_id: str,
    session: dict = Depends(require_patient_session),
    repo=Depends(get_queue_repo),
):
    """Get detailed information about a specific report/queue entry.

    Returns test details, status timeline, and doctor's notes.
    Only returns entries belonging to the authenticated patient.
    """
    entry = await repo.get_by_id(entry_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )

    # Security: only the owning patient can view
    if str(entry.patient_uuid) != str(session["patient_uuid"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this report.",
        )

    return {
        "entry_id": str(entry.id),
        "service_code": entry.service_code,
        "service_name": entry.service_name,
        "token_number": entry.token_number,
        "room": entry.room,
        "department": entry.department,
        "status": entry.status.value if entry.status else None,
        "visit_id": entry.visit_id,
        "patient_name": entry.patient_name,
        "notes": entry.notes or "",
        "timestamps": {
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "called_at": entry.called_at.isoformat() if entry.called_at else None,
            "started_at": entry.started_at.isoformat() if entry.started_at else None,
            "completed_at": entry.completed_at.isoformat() if entry.completed_at else None,
            "report_ready_at": entry.report_ready_at.isoformat() if entry.report_ready_at else None,
            "delivered_at": entry.delivered_at.isoformat() if entry.delivered_at else None,
        },
    }


# =============================================================================
# Feedback
# =============================================================================


@api_router.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="Submit patient feedback",
)
async def submit_feedback(
    request: FeedbackRequest,
    session: dict = Depends(require_patient_session),
    use_case: FeedbackUseCase = Depends(get_feedback_use_case),
):
    """Submit post-visit feedback with rating and optional comment.

    - rating: 1-5 star rating
    - comment: Optional text feedback (max 2000 chars)
    """
    command = Command(data={
        "patient_uuid": session["patient_uuid"],
        "patient_id": session["patient_id"],
        "rating": request.rating,
        "comment": request.comment,
    })
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    return result.data


# =============================================================================
# PWA Pages (HTML)
# =============================================================================


def _render_template(template_path: Path) -> str:
    """Read a template and substitute clinic settings variables.

    Supports: {{CLINIC_NAME}}, {{CLINIC_SPECIALTY}}, {{CLINIC_LOGO}}

    Args:
        template_path: Path to the HTML template file.

    Returns:
        HTML string with all variables substituted.
    """
    cs = get_clinic_settings()
    html = template_path.read_text(encoding="utf-8")
    html = html.replace("{{CLINIC_NAME}}", cs.name)
    html = html.replace("{{CLINIC_SPECIALTY}}", cs.specialty)
    html = html.replace("{{CLINIC_LOGO}}", cs.logo_emoji)
    return html


@router.get("/experience/", response_class=HTMLResponse, include_in_schema=False)
@router.get("/experience/login", response_class=HTMLResponse, include_in_schema=False)
async def pwa_login_page():
    """Serve the PWA login page."""
    html_path = PWA_DIR / "templates" / "login.html"
    return HTMLResponse(content=_render_template(html_path))


@router.get("/experience/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def pwa_dashboard_page():
    """Serve the PWA dashboard page."""
    html_path = PWA_DIR / "templates" / "dashboard.html"
    return HTMLResponse(content=_render_template(html_path))


@router.get("/experience/manifest.json", include_in_schema=False)
async def pwa_manifest():
    """Serve the PWA manifest."""
    manifest_path = PWA_DIR / "manifest.json"
    return FileResponse(str(manifest_path), media_type="application/manifest+json")


@router.get("/experience/service-worker.js", include_in_schema=False)
async def pwa_service_worker():
    """Serve the service worker."""
    sw_path = PWA_DIR / "service-worker.js"
    return FileResponse(
        str(sw_path),
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )
