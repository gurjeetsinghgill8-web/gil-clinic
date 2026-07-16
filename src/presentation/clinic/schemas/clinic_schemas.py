"""Clinic Engine — Pydantic v2 schemas.

Schemas for clinic settings API endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ClinicSettingsResponse(BaseModel):
    """Response schema for clinic settings."""

    name: str = Field(default="GIL CLINIC", description="Clinic name")
    specialty: str = Field(default="Cardiology", description="Clinic specialty")
    logo_emoji: str = Field(default="🏥", description="Logo emoji")
    phone: str = Field(default="", description="Contact phone number")
    address: str = Field(default="", description="Clinic address")
    doctor_name: str = Field(
        default="Dr. Gurjeet Singh Gill",
        description="Doctor name for display",
    )


class ClinicSettingsUpdateRequest(BaseModel):
    """Request schema for updating clinic settings.

    All fields are optional — only provided fields are updated.
    """

    name: str | None = Field(default=None, description="Clinic name")
    specialty: str | None = Field(default=None, description="Clinic specialty")
    logo_emoji: str | None = Field(default=None, description="Logo emoji")
    phone: str | None = Field(default=None, description="Contact phone number")
    address: str | None = Field(default=None, description="Clinic address")
    doctor_name: str | None = Field(
        default=None, description="Doctor name for display"
    )


class ClinicSettingsUpdateResponse(BaseModel):
    """Response after updating clinic settings."""

    message: str = Field(default="Clinic settings updated")
    settings: ClinicSettingsResponse


# =============================================================================
# Department Schemas
# =============================================================================


class DepartmentResponse(BaseModel):
    """Response schema for a single department."""

    code: str = Field(..., description="Unique department code")
    name: str = Field(..., description="Display name")
    description: str = Field(default="", description="Description")
    is_active: bool = Field(default=True, description="Whether active")
    display_order: int = Field(default=0, description="Sort order")
    created_at: str | None = Field(default=None)
    updated_at: str | None = Field(default=None)


class DepartmentCreateRequest(BaseModel):
    """Request schema for creating a department."""

    code: str = Field(..., min_length=1, max_length=50, description="Unique code (e.g., CARDIO)")
    name: str = Field(..., min_length=1, max_length=200, description="Display name")
    description: str = Field(default="", max_length=500, description="Description")
    display_order: int = Field(default=0, description="Sort order (lower = first)")


class DepartmentUpdateRequest(BaseModel):
    """Request schema for updating a department. All fields optional."""

    name: str | None = Field(default=None, max_length=200, description="Display name")
    description: str | None = Field(default=None, max_length=500, description="Description")
    is_active: bool | None = Field(default=None, description="Whether active")
    display_order: int | None = Field(default=None, description="Sort order")


class DepartmentListResponse(BaseModel):
    """Response schema for listing departments."""

    departments: list[DepartmentResponse]
    total: int


class DepartmentSingleResponse(BaseModel):
    """Response schema for a single department operation."""

    department: DepartmentResponse
    message: str = Field(default="")


class DepartmentDeleteResponse(BaseModel):
    """Response schema for deleting a department."""

    message: str = Field(default="Department deleted")


# =============================================================================
# Service Schemas
# =============================================================================


class ServiceResponse(BaseModel):
    """Response schema for a single service."""

    code: str = Field(..., description="Unique service code (e.g., ECG)")
    display_name: str = Field(..., description="Full display name")
    department_code: str = Field(..., description="Parent department code")
    room_name: str = Field(default="", description="Default room name")
    avg_test_time: int = Field(default=10, description="Average test time in minutes")
    is_active: bool = Field(default=True, description="Whether active")
    created_at: str | None = Field(default=None)
    updated_at: str | None = Field(default=None)


class ServiceCreateRequest(BaseModel):
    """Request schema for creating a service."""

    code: str = Field(..., min_length=1, max_length=50, description="Unique code (e.g., ECG)")
    display_name: str = Field(..., min_length=1, max_length=200, description="Full display name")
    department_code: str = Field(..., min_length=1, max_length=50, description="Parent department code")
    room_name: str = Field(default="", max_length=200, description="Default room name")
    avg_test_time: int = Field(default=10, ge=1, le=999, description="Average test time in minutes")


class ServiceUpdateRequest(BaseModel):
    """Request schema for updating a service. All fields optional."""

    display_name: str | None = Field(default=None, max_length=200, description="Full display name")
    room_name: str | None = Field(default=None, max_length=200, description="Default room name")
    avg_test_time: int | None = Field(default=None, ge=1, le=999, description="Average test time in minutes")
    is_active: bool | None = Field(default=None, description="Whether active")
    department_code: str | None = Field(default=None, description="New parent department code")


class ServiceListResponse(BaseModel):
    """Response schema for listing services."""

    services: list[ServiceResponse]
    total: int


class ServiceSingleResponse(BaseModel):
    """Response schema for a single service operation."""

    service: ServiceResponse
    message: str = Field(default="")


class ServiceDeleteResponse(BaseModel):
    """Response schema for deleting a service."""

    message: str = Field(default="Service deleted")
