"""Pydantic v2 schemas for Patient API requests and responses.

These are the HTTP layer schemas — distinct from application DTOs.
They handle request validation, response formatting, and OpenAPI docs.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Enums
# =============================================================================


class GenderEnum(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


# =============================================================================
# Request Schemas
# =============================================================================


class RegisterPatientRequest(BaseModel):
    """Register a new patient."""

    name: str = Field(..., min_length=1, max_length=200, example="Ramesh Kumar")
    age: int = Field(..., ge=1, le=150, example=45)
    gender: GenderEnum = Field(..., example="male")
    phone: str = Field(..., pattern=r"^\d{10}$", example="9876543210")
    email: str | None = Field(None, max_length=200, example="ramesh@email.com")
    address: str | None = Field(None, max_length=500)
    date_of_birth: date | None = None
    blood_group: str | None = Field(
        None, pattern=r"^(A|B|AB|O)[+-]$", example="B+"
    )
    emergency_contact_name: str | None = Field(None, max_length=200)
    emergency_contact_relationship: str | None = Field(None, max_length=100)
    emergency_contact_phone: str | None = Field(None, pattern=r"^\d{10}$")
    source: str = Field("walk-in", description="Registration source (walk-in, referral, online)")


class UpdatePatientRequest(BaseModel):
    """Update patient information."""

    name: str | None = Field(None, min_length=1, max_length=200)
    age: int | None = Field(None, ge=1, le=150)
    gender: GenderEnum | None = None
    email: str | None = Field(None, max_length=200)
    address: str | None = Field(None, max_length=500)
    date_of_birth: date | None = None
    blood_group: str | None = Field(None, pattern=r"^(A|B|AB|O)[+-]$")
    emergency_contact_name: str | None = Field(None, max_length=200)
    emergency_contact_relationship: str | None = Field(None, max_length=100)
    emergency_contact_phone: str | None = Field(None, pattern=r"^\d{10}$")


class RegisterDeviceRequest(BaseModel):
    """Register a device for PWA notifications."""

    device_id: str = Field(..., min_length=1, max_length=500)
    device_name: str | None = Field(None, max_length=200)
    push_token: str | None = Field(None, max_length=1000)
    platform: str = Field("web", pattern=r"^(web|android|ios)$")
    user_agent: str | None = Field(None, max_length=500)


class UpdateNotificationPreferencesRequest(BaseModel):
    """Update notification channel preferences."""

    push_enabled: bool | None = None
    sms_enabled: bool | None = None
    whatsapp_enabled: bool | None = None
    email_enabled: bool | None = None
    sound_enabled: bool | None = None
    vibration_enabled: bool | None = None


class AddMedicalHistoryRequest(BaseModel):
    """Add a medical history entry."""

    condition: str = Field(..., min_length=1, max_length=300, example="Hypertension")
    diagnosed_at: str | None = Field(None, max_length=100, example="2024-01")
    notes: str | None = Field(None, max_length=1000)
    is_active: bool = True


class SetInquiryRequest(BaseModel):
    """Set a reception inquiry from patient PWA."""

    inquiry_text: str = Field(..., min_length=1, max_length=1000)


class BlockPatientRequest(BaseModel):
    """Block a patient account."""

    reason: str = Field(..., min_length=1, max_length=500)


class MergePatientsRequest(BaseModel):
    """Merge duplicate patient records."""

    source_patient_id: str = Field(..., description="Patient to merge FROM (will be deactivated)")
    target_patient_id: str = Field(..., description="Patient to merge INTO (survivor)")


# =============================================================================
# Response Schemas
# =============================================================================


class DeviceResponse(BaseModel):
    """Device registration info in API responses."""

    device_id: str
    device_name: str | None = None
    platform: str
    registered_at: datetime
    last_seen_at: datetime


class NotificationPreferencesResponse(BaseModel):
    """Notification preferences in API responses."""

    push_enabled: bool
    sms_enabled: bool
    whatsapp_enabled: bool
    email_enabled: bool
    sound_enabled: bool
    vibration_enabled: bool


class MedicalHistoryEntryResponse(BaseModel):
    """Medical history entry in API responses."""

    condition: str
    diagnosed_at: str | None = None
    notes: str | None = None
    is_active: bool
    recorded_at: str


class PatientResponse(BaseModel):
    """Patient data in API responses."""

    id: str
    patient_id: str
    name: str
    age: int
    gender: str
    phone: str
    email: str | None = None
    address: str | None = None
    date_of_birth: str | None = None
    blood_group: str | None = None
    status: str
    emergency_contact_name: str | None = None
    emergency_contact_relationship: str | None = None
    emergency_contact_phone: str | None = None
    total_visits: int
    last_visit_at: str | None = None
    has_qr_identity: bool
    device_count: int
    notification_preferences: NotificationPreferencesResponse | None = None
    reception_inquiry: str | None = None
    created_at: str
    updated_at: str


class PatientListResponse(BaseModel):
    """Paginated patient list."""

    patients: list[PatientResponse]
    total: int
    offset: int
    limit: int


class RegisterPatientResponse(BaseModel):
    """Response after patient registration."""

    id: str
    patient_id: str
    name: str
    phone: str
    message: str = "Patient registered successfully"


class DeviceRegisteredResponse(BaseModel):
    """Response after device registration."""

    device_id: str
    message: str = "Device registered successfully"


class DeviceRemovedResponse(BaseModel):
    """Response after device removal."""

    message: str = "Device removed successfully"


class InquiryResponse(BaseModel):
    """Response after inquiry."""

    patient_id: str
    inquiry_text: str
    message: str = "Inquiry sent to reception"


class StatusChangeResponse(BaseModel):
    """Response after status change."""

    patient_id: str
    old_status: str
    new_status: str
    message: str


class MergeResponse(BaseModel):
    """Response after patient merge."""

    source_patient_id: str
    target_patient_id: str
    message: str


class VisitRecordResponse(BaseModel):
    """Response after recording a visit."""

    patient_id: str
    visit_number: int
    last_visit_at: str | None = None
    message: str


class TimelineResponse(BaseModel):
    """Patient timeline / visit history."""

    patient_id: str
    name: str
    total_visits: int
    first_visit: bool
    last_visit_at: str | None = None
    days_since_last_visit: int | None = None
    status: str
    device_count: int
    has_qr_identity: bool


class MedicalHistoryResponse(BaseModel):
    """Medical history list response."""

    patient_id: str
    entries: list[MedicalHistoryEntryResponse]
    count: int


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    code: str | None = None
