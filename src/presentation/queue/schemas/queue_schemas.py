"""Queue Lite — Pydantic v2 request/response schemas for FastAPI."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# =============================================================================
# Request Schemas
# =============================================================================


class CreateQueueRequest(BaseModel):
    """Reception creates queue entries for a patient's tests."""

    patient_id: str = Field(..., description="Patient ID (CQ-YYYYMMDD-NNN)")
    services: list[str] = Field(
        ..., min_length=1, description="Service codes: ECG, Echo, TMT, etc."
    )
    created_by: str = Field("reception", description="Staff ID who created this")


class TechnicianActionRequest(BaseModel):
    """Single action on a queue entry."""

    entry_id: str = Field(..., description="Queue entry UUID")
    action: str = Field(
        ...,
        description="Action: call, recall, start, complete, report-ready, deliver, cancel, no-show",
    )
    updated_by: str = Field("technician", description="Staff ID")
    reason: Optional[str] = Field(None, description="Reason (for cancel action)")


# =============================================================================
# Response Schemas
# =============================================================================


class QueueEntryResponse(BaseModel):
    """A single queue entry in API responses."""

    id: str
    visit_id: str
    patient_id: str
    patient_name: str
    service_code: str
    service_name: str
    token_number: int
    room: str
    status: str
    status_display: str
    is_active: bool
    display_order: int
    called_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    report_ready_at: Optional[str] = None
    delivered_at: Optional[str] = None
    created_at: str


class CreateQueueResponse(BaseModel):
    """Response after creating queue entries."""

    visit_id: str
    patient_id: str
    patient_name: str
    entries: list[QueueEntryResponse]
    total_entries: int
    message: str


class DashboardStats(BaseModel):
    """Dashboard summary counts."""

    waiting: int = 0
    called: int = 0
    in_progress: int = 0
    active: int = 0


class ListQueueResponse(BaseModel):
    """Department queue listing."""

    department: str
    total: int
    stats: DashboardStats
    entries: list[QueueEntryResponse]


class ActionResponse(BaseModel):
    """Response after a technician action."""

    id: str
    patient_name: str
    service_code: str
    token_number: int
    previous_status: str
    action: str
    timestamp: str
    message: str


class PatientEntryResponse(BaseModel):
    """Queue entry for patient PWA view with wait time."""

    id: str
    service_code: str
    service_name: str
    token_number: int
    status: str
    status_display: str
    room: str
    queue_position: int
    wait_minutes: int
    called_at: Optional[str] = None
    started_at: Optional[str] = None


class PatientQueueResponse(BaseModel):
    """Patient's personal queue status."""

    patient_id: str
    patient_name: str
    total_visits: int
    entries: list[PatientEntryResponse]
    active_count: int


# =============================================================================
# Doctor Dashboard
# =============================================================================


class DoctorStats(BaseModel):
    """Doctor dashboard summary counts."""

    pending_review: int = 0
    ready_for_delivery: int = 0
    total: int = 0


class DoctorEntryResponse(BaseModel):
    """Queue entry for doctor dashboard with patient demographics."""

    id: str
    visit_id: str
    patient_id: str
    patient_uuid: str
    patient_name: str
    age: int | None = None
    gender: str | None = None
    service_code: str
    service_name: str
    token_number: int
    department: str
    room: str
    status: str
    status_display: str
    created_by: str
    called_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    report_ready_at: str | None = None
    elapsed_minutes: int | None = None
    created_at: str


class DoctorDashboardResponse(BaseModel):
    """Doctor's composite queue dashboard."""

    stats: DoctorStats
    pending_review: list[DoctorEntryResponse]
    ready_for_delivery: list[DoctorEntryResponse]


# =============================================================================
# Doctor Workspace (V2 — Enhanced)
# =============================================================================


class TestInfo(BaseModel):
    """Single test in a visit group."""

    id: str
    service_code: str
    service_name: str
    token_number: int
    status: str
    status_display: str


class VisitGroup(BaseModel):
    """Queue entries grouped by visit_id with patient info."""

    id: str
    visit_id: str
    patient_id: str
    patient_uuid: str
    patient_name: str
    age: int | None = None
    gender: str | None = None
    phone: str | None = None
    blood_group: str | None = None
    medical_history: list[dict] = []
    notes: str = ""
    alert_message: str | None = None
    service_code: str
    service_name: str
    token_number: int
    department: str
    room: str
    status: str
    status_display: str
    created_by: str
    called_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    report_ready_at: str | None = None
    elapsed_minutes: int | None = None
    created_at: str
    tests: list[TestInfo] = []


class DoctorWorkspaceStats(BaseModel):
    """Doctor workspace summary counts."""

    consultation: int = 0
    pending_review: int = 0
    ready_for_delivery: int = 0
    total: int = 0


class DoctorWorkspaceResponse(BaseModel):
    """Doctor's full workspace with grouped visits."""

    stats: DoctorWorkspaceStats
    consultation_queue: list[VisitGroup] = []
    pending_review: list[VisitGroup] = []
    ready_for_delivery: list[VisitGroup] = []
    pending_review_flat: list[dict] = []
    ready_for_delivery_flat: list[dict] = []


# =============================================================================
# Alert System
# =============================================================================


class SendAlertRequest(BaseModel):
    """Send an alert/reminder to a patient's phone."""

    entry_id: str = Field(..., description="Queue entry UUID")
    message: str = Field("", description="Alert message to display on patient's phone")
    updated_by: str = Field("technician", description="Staff ID")


class AlertResponse(BaseModel):
    """Response after sending an alert."""

    entry_id: str
    patient_name: str
    message: str
    sent: bool


class AlertStatusResponse(BaseModel):
    """Response for patient checking their alert status."""

    alert: bool
    message: str | None = None
    room: str | None = None
    service_code: str | None = None
    service_name: str | None = None
    token_number: int | None = None


# =============================================================================
# TV Alert System
# =============================================================================


class TvAlertSendRequest(BaseModel):
    """Send a broadcast alert to TV displays."""

    message: str = Field(..., min_length=1, max_length=500, description="Alert message")
    severity: str = Field("info", description="Severity: info, warning, emergency")
    duration_seconds: int = Field(30, ge=5, le=300, description="Display duration")


class TvAlertResponse(BaseModel):
    """TV alert response."""

    status: str = "ok"
    alert: dict | None = None
    message: str = ""


# =============================================================================
# Manager Dashboard
# =============================================================================


class ManagerStats(BaseModel):
    """Manager dashboard KPI stats."""

    patients_today: int = 0
    tests_today: int = 0
    completed_today: int = 0
    avg_wait_minutes: float = 0.0
    completion_rate_pct: float = 0.0


class DepartmentLoadItem(BaseModel):
    """Per-department load summary."""

    code: str
    name: str
    waiting: int = 0
    called: int = 0
    in_progress: int = 0
    active: int = 0
    completed: int = 0
    load_pct: float = 0.0


class ActivityItem(BaseModel):
    """Recent audit activity entry."""

    time: str | None = None
    action: str = ""
    action_label: str = ""
    actor: str = ""
    patient_name: str = ""
    service_code: str = ""
    token_number: int | None = None


class DailyTrendItem(BaseModel):
    """Daily creation/completion counts."""

    date: str = ""
    created: int = 0
    completed: int = 0


class ServiceStatsItem(BaseModel):
    """Per-service performance stats."""

    service_code: str = ""
    service_name: str = ""
    count: int = 0
    avg_wait_minutes: float = 0.0


class ManagerDashboardResponse(BaseModel):
    """Full manager dashboard composite response."""

    stats: ManagerStats
    department_load: list[DepartmentLoadItem] = []
    recent_activity: list[ActivityItem] = []
    daily_trend: list[DailyTrendItem] = []
    service_stats: list[ServiceStatsItem] = []
