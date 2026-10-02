"""Patient application DTOs (Data Transfer Objects).

All DTOs use Pydantic v2 for validation and serialization.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Enums
# =============================================================================


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class PatientStatusEnum(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"
    MERGED = "merged"


# =============================================================================
# Request DTOs
# =============================================================================


class RegisterPatientRequest(BaseModel):
    """Request to register a new patient."""

    name: str = Field(..., min_length=1, max_length=200, description="Full name")
    age: int = Field(..., ge=1, le=150, description="Age in years")
    gender: Gender = Field(..., description="Gender")
    phone: str = Field(..., pattern=r"^\d{10}$", description="10-digit mobile number")
    email: str | None = Field(None, max_length=200, description="Email address")
    address: str | None = Field(None, max_length=500, description="Residential address")
    date_of_birth: date | None = Field(None, description="Date of birth")
    blood_group: str | None = Field(
        None, pattern=r"^(A|B|AB|O)[+-]$", description="Blood group (A+, B-, O+, etc.)"
    )
    emergency_contact_name: str | None = Field(None, max_length=200)
    emergency_contact_relationship: str | None = Field(None, max_length=100)
    emergency_contact_phone: str | None = Field(None, pattern=r"^\d{10}$")
    source: str = Field("reception", description="Registration source")

    @field_validator("emergency_contact_phone")
    @classmethod
    def validate_emergency_phone(cls, v: str | None, info: Any) -> str | None:
        if v and info.data.get("emergency_contact_name") and not v:
            raise ValueError("Emergency contact phone is required when name is provided")
        return v


class UpdatePatientRequest(BaseModel):
    """Request to update patient demographics/contact."""

    name: str | None = Field(None, min_length=1, max_length=200)
    age: int | None = Field(None, ge=1, le=150)
    gender: Gender | None = None
    email: str | None = Field(None, max_length=200)
    address: str | None = Field(None, max_length=500)
    date_of_birth: date | None = None
    blood_group: str | None = Field(None, pattern=r"^(A|B|AB|O)[+-]$")
    emergency_contact_name: str | None = Field(None, max_length=200)
    emergency_contact_relationship: str | None = Field(None, max_length=100)
    emergency_contact_phone: str | None = Field(None, pattern=r"^\d{10}$")


class RegisterDeviceRequest(BaseModel):
    """Request to register a device for PWA notifications."""

    device_id: str = Field(..., min_length=1, max_length=500, description="Unique device identifier")
    device_name: str | None = Field(None, max_length=200, description="Human-readable device name")
    push_token: str | None = Field(None, max_length=1000, description="Push notification token")
    platform: str = Field("web", description="Platform: web, android, ios")
    user_agent: str | None = Field(None, max_length=500)
    ip_address: str | None = Field(None, max_length=50)


class UpdateNotificationPreferencesRequest(BaseModel):
    """Request to update notification preferences."""

    push_enabled: bool | None = None
    sms_enabled: bool | None = None
    whatsapp_enabled: bool | None = None
    email_enabled: bool | None = None
    sound_enabled: bool | None = None
    vibration_enabled: bool | None = None


class AddMedicalHistoryRequest(BaseModel):
    """Request to add a medical history entry."""

    condition: str = Field(..., min_length=1, max_length=300)
    diagnosed_at: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=1000)
    is_active: bool = True


class SetInquiryRequest(BaseModel):
    """Request to set a reception inquiry (from patient PWA)."""

    inquiry_text: str = Field(..., min_length=1, max_length=1000)


class BlockPatientRequest(BaseModel):
    """Request to block a patient."""

    reason: str = Field(..., min_length=1, max_length=500)


class MergePatientsRequest(BaseModel):
    """Request to merge duplicate patient records."""

    source_patient_id: str = Field(..., description="Patient ID to merge FROM (will be deactivated)")
    target_patient_id: str = Field(..., description="Patient ID to merge INTO (survivor)")


class SearchPatientsRequest(BaseModel):
    """Request to search patients."""

    query: str = Field(..., min_length=1, max_length=200, description="Search query (name)")


# =============================================================================
# Response DTOs
# =============================================================================


class DeviceResponse(BaseModel):
    """Device registration in API responses."""

    device_id: str
    device_name: str | None = None
    platform: str
    registered_at: datetime
    last_seen_at: datetime


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
    """Response after successful patient registration."""

    id: str
    patient_id: str
    name: str
    phone: str
    qr_identity: dict[str, Any] | None = None
    message: str = "Patient registered successfully"


class DeviceRegisteredResponse(BaseModel):
    """Response after device registration."""

    device_id: str
    message: str = "Device registered successfully"


class DeviceRemovedResponse(BaseModel):
    """Response after device removal."""

    device_id: str
    message: str = "Device removed successfully"


class NotificationPreferencesResponse(BaseModel):
    """Notification preferences in API responses."""

    push_enabled: bool
    sms_enabled: bool
    whatsapp_enabled: bool
    email_enabled: bool
    sound_enabled: bool
    vibration_enabled: bool


class InquiryResponse(BaseModel):
    """Response after setting an inquiry."""

    patient_id: str
    inquiry_text: str
    message: str = "Inquiry sent to reception"


class PatientStatusChangeResponse(BaseModel):
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


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    code: str | None = None
