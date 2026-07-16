"""Queue Lite — FastAPI routes.

API Contract:
    POST   /api/v1/queue/create          — Reception creates queue entries for patient tests
    GET    /api/v1/queue/dashboard        — Technician dashboard — list department queue
    POST   /api/v1/queue/action           — Technician action: call, start, complete, etc.
    POST   /api/v1/queue/alert            — Technician sends alert/reminder to patient
    GET    /api/v1/queue/patient/{uuid}   — Patient PWA — personal queue status
    GET    /queue/technician-dashboard    — Technician PWA HTML page
    GET    /queue/reception-dashboard     — Reception PWA HTML page
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, StreamingResponse

from src.application.common.command import Command
from src.infrastructure.clinic.settings_provider import get_clinic_settings
from src.presentation.queue.schemas.queue_schemas import (
    CreateQueueRequest,
    CreateQueueResponse,
    TechnicianActionRequest,
    ActionResponse,
    ListQueueResponse,
    PatientQueueResponse,
    SendAlertRequest,
    AlertResponse,
    AlertStatusResponse,
    TvAlertSendRequest,
    TvAlertResponse,
)
from src.presentation.queue.dependencies.queue_dependencies import (
    get_create_queue_use_case,
    get_list_queue_use_case,
    get_technician_action_use_case,
    get_patient_queue_use_case,
    get_doctor_queue_use_case,
    get_alert_use_case,
    get_manager_dashboard_use_case,
    get_tv_alert_use_case,
    get_queue_repo,
    get_patient_repo,
)

router = APIRouter(prefix="/api/v1/queue", tags=["Queue"])


# =============================================================================
# Create Queue (Reception)
# =============================================================================


@router.post(
    "/create",
    response_model=CreateQueueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create queue entries for patient tests (Reception)",
)
async def create_queue(
    request: CreateQueueRequest,
    use_case=Depends(get_create_queue_use_case),
):
    """Register a patient for tests and create queue entries.

    Reception selects patient + tests → generates queue entries with tokens.
    Each test gets its own queue entry with a sequential token number.
    """
    command = Command(data={
        "patient_id": request.patient_id,
        "services": request.services,
        "created_by": request.created_by,
    })
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    return result.data


# =============================================================================
# Department Dashboard (Technician)
# =============================================================================


@router.get(
    "/dashboard",
    response_model=ListQueueResponse,
    summary="Get department queue (Technician Dashboard)",
)
async def list_department_queue(
    department: str = "Cardiology",
    status_filter: str | None = Query(None, alias="status"),
    offset: int = 0,
    limit: int = 100,
    use_case=Depends(get_list_queue_use_case),
):
    """Get today's queue for a department, with optional status filter.

    Returns active entries first, sorted by status order and token number.
    Includes dashboard stats (waiting/called/in_progress counts).
    """
    command = Command(data={
        "department": department,
        "status": status_filter,
        "offset": offset,
        "limit": limit,
    })
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    return result.data


# =============================================================================
# Technician Action
# =============================================================================


@router.post(
    "/action",
    response_model=ActionResponse,
    summary="Perform action on a queue entry (Technician)",
)
async def technician_action(
    request: TechnicianActionRequest,
    use_case=Depends(get_technician_action_use_case),
):
    """Perform a status transition on a queue entry.

    Actions: call, recall, start, complete, report-ready, deliver, cancel, no-show.

    Validates the transition — returns 400 if not allowed.
    """
    command = Command(data={
        "entry_id": request.entry_id,
        "action": request.action,
        "updated_by": request.updated_by,
        "reason": request.reason,
    })
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    return result.data


# =============================================================================
# Alert System — Send Alert to Patient
# =============================================================================


@router.post(
    "/alert",
    response_model=AlertResponse,
    summary="Send alert/reminder to patient's phone",
)
async def send_alert(
    request: SendAlertRequest,
    use_case=Depends(get_alert_use_case),
):
    """Send a browser notification (beep + vibrate) to the patient's phone.

    Only works for WAITING or CALLED queue entries.
    The alert message will be displayed as a banner on the patient's PWA.
    """
    command = Command(data={
        "entry_id": request.entry_id,
        "message": request.message,
        "updated_by": request.updated_by,
    })
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    return result.data


# =============================================================================
# Patient Queue Status (Patient PWA)
# =============================================================================


@router.get(
    "/patient/{patient_uuid}",
    response_model=PatientQueueResponse,
    summary="Get patient's queue status (Patient PWA)",
)
async def patient_queue(
    patient_uuid: str,
    use_case=Depends(get_patient_queue_use_case),
):
    """Get the current queue status for a patient.

    Returns all active queue entries with wait time, ETA, and queue position.
    This is the endpoint the PWA dashboard calls for live status updates.
    """
    command = Command(data={
        "patient_uuid": patient_uuid,
    })
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error,
        )

    return result.data


# =============================================================================
# Doctor Dashboard (Composite View)
# =============================================================================


@router.get(
    "/doctor-dashboard",
    summary="Doctor Dashboard — composite queue view",
    include_in_schema=False,
)
async def doctor_dashboard_api(
    limit: int = 100,
    use_case=Depends(get_doctor_queue_use_case),
):
    """Get the doctor's composite queue dashboard.

    Returns completed tests pending review and reports ready for delivery,
    enriched with patient demographics, across all departments.
    """
    from src.presentation.queue.schemas.queue_schemas import (
        DoctorDashboardResponse,
    )

    command = Command(data={"limit": limit})
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error,
        )

    return DoctorDashboardResponse(**result.data)


@router.get(
    "/doctor-workspace",
    summary="Doctor Workspace — full composite view with consultation queue",
    include_in_schema=False,
)
async def doctor_workspace_api(
    limit: int = 100,
    use_case=Depends(get_doctor_queue_use_case),
):
    """Get the doctor's full workspace.

    Returns:
        - consultation_queue: WAITING + CALLED entries grouped by visit
        - pending_review: COMPLETED entries grouped by visit
        - ready_for_delivery: REPORT_READY entries grouped by visit
        - All enriched with patient demographics and grouped by visit_id.
    """
    from src.presentation.queue.schemas.queue_schemas import (
        DoctorWorkspaceResponse,
    )

    command = Command(data={"limit": limit})
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error,
        )

    return DoctorWorkspaceResponse(**result.data)


# =============================================================================
# Templates directory
# =============================================================================

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _render_queue_template(template_name: str) -> str:
    """Read a template and substitute clinic settings variables.

    Args:
        template_name: Name of the template file (e.g. 'technician_dashboard.html').

    Returns:
        HTML string with all variables substituted.

    Raises:
        HTTPException: If template file is not found.
    """
    html_path = TEMPLATES_DIR / template_name
    if not html_path.exists():
        raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")
    cs = get_clinic_settings()
    html = html_path.read_text(encoding="utf-8")
    html = html.replace("{{CLINIC_NAME}}", cs.name)
    html = html.replace("{{CLINIC_SPECIALTY}}", cs.specialty)
    html = html.replace("{{CLINIC_LOGO}}", cs.logo_emoji)
    return html


@router.get(
    "/technician-dashboard",
    response_class=HTMLResponse,
    summary="Technician Dashboard PWA",
    include_in_schema=False,
)
async def technician_dashboard():
    """Serve the Technician Dashboard PWA page."""
    return HTMLResponse(content=_render_queue_template("technician_dashboard.html"))


@router.get(
    "/reception-dashboard",
    response_class=HTMLResponse,
    summary="Reception Dashboard PWA",
    include_in_schema=False,
)
async def reception_dashboard():
    """Serve the Reception Dashboard PWA page."""
    return HTMLResponse(content=_render_queue_template("reception_dashboard.html"))


@router.get(
    "/tv-display",
    response_class=HTMLResponse,
    summary="Live TV Display for waiting room",
    include_in_schema=False,
)
async def tv_display():
    """Serve the Live TV Display page for waiting area monitor."""
    return HTMLResponse(content=_render_queue_template("tv_display.html"))


# =============================================================================
# TV Alert — Broadcast message to waiting area displays
# =============================================================================


@router.post(
    "/tv-alert",
    response_model=TvAlertResponse,
    summary="Send a broadcast alert to TV displays",
)
async def send_tv_alert(
    request: TvAlertSendRequest,
    use_case=Depends(get_tv_alert_use_case),
):
    """Send a broadcast alert to all TV displays in the waiting area.

    Three severity levels:
    - info: Blue banner, auto-dismiss 10s
    - warning: Amber pulsing banner, dismiss button, auto-dismiss 30s
    - emergency: Full-screen red overlay, requires confirmation

    Staff can send alerts from the reception or technician dashboard.
    """
    command = Command(data={
        "operation": "send",
        "message": request.message,
        "severity": request.severity,
        "duration_seconds": request.duration_seconds,
    })
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    return result.data


@router.get(
    "/tv-alert",
    response_model=TvAlertResponse,
    summary="Check for pending TV alerts",
)
async def check_tv_alert(
    use_case=Depends(get_tv_alert_use_case),
):
    """Check for any pending broadcast alerts for TV displays.

    Auto-clears after being read. TV displays should poll this
    every refresh cycle.
    """
    command = Command(data={"operation": "check"})
    result = await use_case.run(command)

    if result.is_fail:
        return TvAlertResponse(status="error", message=result.error)

    return result.data


# =============================================================================
# Doctor's Clinical Notes — Save/Retrieve
# =============================================================================


@router.post(
    "/notes",
    summary="Save doctor's clinical notes for a queue entry",
)
async def save_notes(
    request: Request,
    repo=Depends(get_queue_repo),
):
    """Save clinical/consultation notes for a queue entry.

    Request body: { "entry_id": "...", "notes": "..." }
    Notes are persisted on the QueueEntry and viewable by the patient.
    """
    body = await request.json()
    entry_id = body.get("entry_id")
    notes_text = body.get("notes", "")

    if not entry_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="entry_id is required.",
        )

    entry = await repo.get_by_id(entry_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue entry not found.",
        )

    entry.notes = notes_text
    entry.touch()
    await repo.save(entry)

    return {"status": "saved", "entry_id": entry_id}


@router.get(
    "/notes/{entry_id}",
    summary="Get clinical notes for a queue entry",
)
async def get_notes(
    entry_id: str,
    repo=Depends(get_queue_repo),
):
    """Retrieve the clinical notes stored on a queue entry."""
    entry = await repo.get_by_id(entry_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue entry not found.",
        )

    return {
        "entry_id": entry_id,
        "notes": entry.notes or "",
        "service_code": entry.service_code,
        "service_name": entry.service_name,
    }


# =============================================================================
# Reports Ready for Delivery (Reception)
# =============================================================================


@router.get(
    "/reports/ready",
    summary="Get all reports ready for delivery (Reception view)",
)
async def reports_ready(
    repo=Depends(get_queue_repo),
    patient_repo=Depends(get_patient_repo),
):
    """Get all REPORT_READY queue entries enriched with patient details.

    Returns a flat list of entries ready for delivery, with patient
    demographics (name, age, gender, phone) included.
    This is the dedicated endpoint for the Reception Reports tab.
    """
    entries = await repo.list_by_status(status="REPORT_READY", limit=200)

    result = []
    for entry in entries:
        patient = None
        if entry.patient_uuid:
            patient = await patient_repo.get_by_uuid(entry.patient_uuid)

        result.append({
            "entry_id": str(entry.id),
            "patient_uuid": entry.patient_uuid,
            "patient_id": entry.patient_id,
            "patient_name": entry.patient_name,
            "patient_age": patient.demographics.age if patient and patient.demographics else None,
            "patient_gender": patient.demographics.gender if patient and patient.demographics else None,
            "patient_phone": patient.contact.phone if patient and patient.contact else None,
            "service_code": entry.service_code,
            "service_name": entry.service_name,
            "token_number": entry.token_number,
            "room": entry.room,
            "department": entry.department,
            "visit_id": entry.visit_id,
            "status": entry.status.value if entry.status else "REPORT_READY",
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "completed_at": entry.completed_at.isoformat() if entry.completed_at else None,
            "report_ready_at": entry.report_ready_at.isoformat() if entry.report_ready_at else None,
        })

    return {
        "total": len(result),
        "reports": result,
    }


@router.get(
    "/doctor-dashboard-page",
    response_class=HTMLResponse,
    summary="Doctor Dashboard PWA",
    include_in_schema=False,
)
async def doctor_dashboard_page():
    """Serve the Doctor Dashboard PWA page."""
    return HTMLResponse(content=_render_queue_template("doctor_dashboard.html"))


# =============================================================================
# Manager Dashboard (Module 4)
# =============================================================================


@router.get(
    "/manager-dashboard",
    summary="Manager Dashboard — full analytics JSON",
)
async def manager_dashboard_api(
    days: int = Query(7, description="Days of trend data to include"),
    use_case=Depends(get_manager_dashboard_use_case),
):
    """Get the manager dashboard analytics data.

    Returns:
        - stats: Today's KPIs (patients, tests, avg wait, completion rate)
        - department_load: Per-department waiting/in-progress/completed counts
        - recent_activity: Today's audit trail
        - daily_trend: Last N days of created vs completed
        - service_stats: Per-service performance
    """
    from src.presentation.queue.schemas.queue_schemas import (
        ManagerDashboardResponse,
    )

    command = Command(data={"days": days})
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error,
        )

    return ManagerDashboardResponse(**result.data)


@router.get(
    "/manager-dashboard-page",
    response_class=HTMLResponse,
    summary="Manager Dashboard PWA",
    include_in_schema=False,
)
async def manager_dashboard_page():
    """Serve the Manager Dashboard PWA page."""
    return HTMLResponse(content=_render_queue_template("manager_dashboard.html"))


@router.get(
    "/manager-export",
    summary="Export queue data as CSV",
    include_in_schema=False,
)
async def manager_export_csv(
    department: str | None = Query(None, description="Filter by department"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    use_case=Depends(get_list_queue_use_case),
):
    """Export today's queue data as a CSV file for spreadsheet analysis."""
    import csv
    import io

    from fastapi.responses import StreamingResponse

    command = Command(data={
        "department": department or "Cardiology",
        "status": status_filter,
        "offset": 0,
        "limit": 5000,
    })
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    entries = result.data.get("entries", [])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Token", "Patient Name", "Service", "Department", "Room",
        "Status", "Created At", "Called At", "Started At",
        "Completed At", "Report Ready At", "Delivered At",
        "Created By", "Visit ID",
    ])
    for e in entries:
        writer.writerow([
            e.get("token_number", ""),
            e.get("patient_name", ""),
            e.get("service_code", ""),
            e.get("department", ""),
            e.get("room", ""),
            e.get("status", ""),
            e.get("created_at", ""),
            e.get("called_at", ""),
            e.get("started_at", ""),
            e.get("completed_at", ""),
            e.get("report_ready_at", ""),
            e.get("delivered_at", ""),
            e.get("created_by", ""),
            e.get("visit_id", ""),
        ])

    output.seek(0)
    filename = f"queue_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "/status-report",
    response_class=HTMLResponse,
    summary="Project Status Report for Management",
    include_in_schema=False,
)
async def status_report():
    """Serve the project status report page (for boss/management review)."""
    return HTMLResponse(content=_render_queue_template("status_report.html"))
