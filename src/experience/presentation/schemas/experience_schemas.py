"""Experience Engine — Pydantic v2 schemas.

These are the HTTP layer schemas for the patient experience API.
All endpoints are designed to be consumed by the PWA.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# Login
# =============================================================================


class PhoneLoginRequest(BaseModel):
    """Login using 10-digit phone number."""

    phone: str = Field(..., pattern=r"^\d{10}$", description="10-digit mobile number")
    method: str = "phone"


class QRLoginRequest(BaseModel):
    """Login using QR scan payload."""

    qr_payload: str = Field(..., min_length=1, description="QR code encrypted payload")
    method: str = "qr"


class PatientIdLoginRequest(BaseModel):
    """Login using patient ID from token slip."""

    patient_id: str = Field(..., min_length=1, description="Patient ID (CQ-YYYYMMDD-NNN)")
    method: str = "patient_id"


class LoginResponse(BaseModel):
    """Response after successful login."""

    session_token: str
    expires_at: str
    patient: dict[str, Any]


# =============================================================================
# Status
# =============================================================================


class PatientInfo(BaseModel):
    """Basic patient info for dashboard display."""

    patient_id: str
    name: str
    age: int
    gender: str
    phone: str


class HospitalInfo(BaseModel):
    """Hospital branding info.

    Populated from ClinicSettings at runtime.
    Defaults here are fallbacks if settings are unavailable.
    """

    name: str = "GIL CLINIC"
    specialty: str = "Cardiology"
    logo_emoji: str = "🏥"


class TestStatus(BaseModel):
    """Single test status for the dashboard."""

    test_name: str
    status: str
    status_display: str
    token_number: int | None = None
    queue_position: int | None = None
    room: str | None = None
    wait_minutes: int = 0
    expected_time: str = "Now / अभी"
    doctor_notes: str | None = None


class StatusResponse(BaseModel):
    """Complete status response for the patient dashboard."""

    patient: PatientInfo
    visit: dict[str, Any]
    tests: list[dict[str, Any]]
    hospital: HospitalInfo
    timestamp: str


# =============================================================================
# Token Slip
# =============================================================================


class TokenSlipResponse(BaseModel):
    """Token slip response with printable HTML."""

    patient_id: str
    name: str
    html: str
    tests: list[dict[str, Any]]
    generated_at: str


# =============================================================================
# Inquiry
# =============================================================================


class InquirySendRequest(BaseModel):
    """Send an inquiry to reception."""

    inquiry_text: str = Field(..., min_length=1, max_length=1000)


class InquiryResponse(BaseModel):
    """Inquiry response."""

    patient_id: str
    inquiry_text: str | None = None
    has_inquiry: bool = False
    status: str = "sent"
    message: str = ""


# =============================================================================
# Feedback
# =============================================================================


class FeedbackRequest(BaseModel):
    """Patient feedback submission."""

    rating: int = Field(..., ge=1, le=5, description="Rating 1-5")
    comment: str = Field("", max_length=2000, description="Optional comment")


class FeedbackResponse(BaseModel):
    """Feedback submission confirmation."""

    status: str
    message: str
    rating: int


# =============================================================================
# Timeline
# =============================================================================


class TimelineEvent(BaseModel):
    """A single event in the patient's journey timeline."""

    type: str = Field(..., description="Event type: registered, waiting, called, in_progress, completed, report_ready, delivered, cancelled, no_show")
    timestamp: str = Field("", description="ISO 8601 timestamp of the event")
    service_name: str = Field("", description="Service/test name")
    service_code: str = Field("", description="Service code")
    token_number: int | None = None
    room: str | None = None
    visit_id: str = Field("", description="Visit this event belongs to")


class VisitTimeline(BaseModel):
    """Timeline events grouped by visit."""

    visit_id: str
    total_tests: int = 0
    services: list[str] = []
    events: list[TimelineEvent] = []


class TimelineResponse(BaseModel):
    """Complete patient timeline response."""

    patient_uuid: str
    total_events: int = 0
    visits: list[VisitTimeline] = []
    all_events: list[TimelineEvent] = []


# =============================================================================
# Error
# =============================================================================


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    code: str | None = None
