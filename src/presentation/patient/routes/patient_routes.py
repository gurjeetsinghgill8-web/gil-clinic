"""Patient API router — all /api/v1/patient endpoints.

Endpoints:
    POST   /api/v1/patient/register          — Register new patient
    GET    /api/v1/patient/lookup            — Lookup patient(s)
    GET    /api/v1/patient/{patient_id}      — Get single patient
    PATCH  /api/v1/patient/{patient_id}      — Update patient
    POST   /api/v1/patient/{patient_id}/block          — Block patient
    POST   /api/v1/patient/{patient_id}/reactivate     — Reactivate patient
    POST   /api/v1/patient/merge             — Merge duplicate records

    POST   /api/v1/patient/{patient_id}/devices           — Register device
    DELETE /api/v1/patient/{patient_id}/devices/{device_id} — Remove device
    PATCH  /api/v1/patient/{patient_id}/preferences       — Update notification prefs

    POST   /api/v1/patient/{patient_id}/visit  — Record visit
    GET    /api/v1/patient/{patient_id}/timeline — Get patient timeline

    POST   /api/v1/patient/{patient_id}/history         — Add medical history
    GET    /api/v1/patient/{patient_id}/history         — List medical history

    POST   /api/v1/patient/{patient_id}/inquiry         — Set inquiry
    DELETE /api/v1/patient/{patient_id}/inquiry          — Clear inquiry
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.application.common.command import Command, Query as CQRSQuery
from src.application.common.exceptions import NotFoundError
from src.application.patient.use_cases.register_patient_use_case import (
    RegisterPatientUseCase,
)
from src.application.patient.use_cases.lookup_patient_use_case import (
    LookupPatientUseCase,
)
from src.application.patient.use_cases.update_patient_use_case import (
    UpdatePatientUseCase,
)
from src.application.patient.use_cases.device_registration_use_case import (
    DeviceRegistrationUseCase,
)
from src.application.patient.use_cases.visit_tracking_use_case import (
    VisitTrackingUseCase,
)
from src.application.patient.use_cases.medical_history_use_case import (
    MedicalHistoryUseCase,
)
from src.presentation.patient.schemas.patient_schemas import (
    RegisterPatientRequest,
    UpdatePatientRequest,
    RegisterDeviceRequest,
    UpdateNotificationPreferencesRequest,
    AddMedicalHistoryRequest,
    SetInquiryRequest,
    BlockPatientRequest,
    MergePatientsRequest,
    PatientResponse,
    PatientListResponse,
    RegisterPatientResponse,
    DeviceRegisteredResponse,
    DeviceRemovedResponse,
    NotificationPreferencesResponse,
    InquiryResponse,
    StatusChangeResponse,
    MergeResponse,
    VisitRecordResponse,
    TimelineResponse,
    MedicalHistoryResponse,
    MedicalHistoryEntryResponse,
    ErrorResponse,
)
from src.presentation.patient.dependencies.use_case_dependencies import (
    get_register_patient_use_case,
    get_lookup_patient_use_case,
    get_update_patient_use_case,
    get_device_registration_use_case,
    get_visit_tracking_use_case,
    get_medical_history_use_case,
)
from src.presentation.identity.dependencies.get_current_user import (
    get_current_user,
    require_role,
)

router = APIRouter(prefix="/api/v1/patient", tags=["patient"])


# =============================================================================
# Registration
# =============================================================================


@router.post(
    "/register",
    response_model=RegisterPatientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new patient",
)
async def register_patient(
    request: RegisterPatientRequest,
    use_case: RegisterPatientUseCase = Depends(get_register_patient_use_case),
    _=Depends(require_role("RECEPTION", "ADMIN", "MANAGER", "DOCTOR")),
) -> RegisterPatientResponse:
    """Register a new patient in the system.

    Generates a patient ID (CQ-YYYYMMDD-NNN), creates QR identity,
    and returns the registration details.
    """
    command = Command(data=request)
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(result.error),
        )

    return result.data


# =============================================================================
# Lookup / Search
# =============================================================================


@router.get(
    "/lookup",
    response_model=PatientListResponse | PatientResponse,
    summary="Lookup patients by phone, QR, name, or list all",
)
async def lookup_patients(
    phone: str | None = Query(None, description="Phone number (10 digits)"),
    qr_hash: str | None = Query(None, description="QR identity hash"),
    query: str | None = Query(None, description="Name search query"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    use_case: LookupPatientUseCase = Depends(get_lookup_patient_use_case),
    _=Depends(require_role("RECEPTION", "ADMIN", "MANAGER", "DOCTOR", "NURSE")),
):
    """Search or list patients.

    Supports lookup by phone, QR hash, name search (fuzzy), or list all.
    """
    params = {}
    if phone:
        import hashlib
        params["phone_hash"] = hashlib.sha256(phone.encode()).hexdigest()
    elif qr_hash:
        params["qr_hash"] = qr_hash
    elif query:
        params["query"] = query

    params["offset"] = offset
    params["limit"] = limit
    if status_filter:
        params["status"] = status_filter

    cqrs_query = CQRSQuery(data=params)
    result = await use_case.run(cqrs_query)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(result.error),
        )

    return result.data


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Get a single patient by ID",
)
async def get_patient(
    patient_id: str,
    use_case: LookupPatientUseCase = Depends(get_lookup_patient_use_case),
    _=Depends(require_role("RECEPTION", "ADMIN", "MANAGER", "DOCTOR", "NURSE")),
) -> PatientResponse:
    """Get a single patient by their human-readable ID (CQ-YYYYMMDD-NNN)."""
    cqrs_query = CQRSQuery(data={"patient_id": patient_id})
    result = await use_case.run(cqrs_query)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(result.error),
        )

    return result.data


# =============================================================================
# Update
# =============================================================================


@router.patch(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Update patient demographics/contact",
)
async def update_patient(
    patient_id: str,
    request: UpdatePatientRequest,
    use_case: UpdatePatientUseCase = Depends(get_update_patient_use_case),
    _=Depends(require_role("RECEPTION", "ADMIN", "MANAGER")),
) -> PatientResponse:
    """Update patient information including demographics, contact, and emergency contact."""
    request.operation = "update"
    request.patient_id = patient_id
    command = Command(data=request)
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(result.error),
        )

    return result.data


@router.post(
    "/{patient_id}/block",
    response_model=StatusChangeResponse,
    summary="Block a patient",
)
async def block_patient(
    patient_id: str,
    request: BlockPatientRequest,
    use_case: UpdatePatientUseCase = Depends(get_update_patient_use_case),
    _=Depends(require_role("ADMIN", "MANAGER")),
) -> StatusChangeResponse:
    """Block a patient for policy violation."""
    request.operation = "block"
    request.patient_id = patient_id
    command = Command(data=request)
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(result.error),
        )

    return result.data


@router.post(
    "/{patient_id}/reactivate",
    response_model=StatusChangeResponse,
    summary="Reactivate a patient",
)
async def reactivate_patient(
    patient_id: str,
    use_case: UpdatePatientUseCase = Depends(get_update_patient_use_case),
    _=Depends(require_role("ADMIN", "MANAGER")),
) -> StatusChangeResponse:
    """Reactivate a previously inactive/blocked patient."""
    command = Command(data={"patient_id": patient_id, "operation": "reactivate"})
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(result.error),
        )

    return result.data


@router.post(
    "/merge",
    response_model=MergeResponse,
    summary="Merge duplicate patient records",
)
async def merge_patients(
    request: MergePatientsRequest,
    use_case: UpdatePatientUseCase = Depends(get_update_patient_use_case),
    _=Depends(require_role("ADMIN")),
) -> MergeResponse:
    """Merge two duplicate patient records into one."""
    request.operation = "merge"
    command = Command(data=request)
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(result.error),
        )

    return result.data


# =============================================================================
# Device Registration (PWA)
# =============================================================================


@router.post(
    "/{patient_id}/devices",
    response_model=DeviceRegisteredResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a device for PWA notifications",
)
async def register_device(
    patient_id: str,
    request: RegisterDeviceRequest,
    use_case: DeviceRegistrationUseCase = Depends(get_device_registration_use_case),
    _=Depends(require_role("RECEPTION", "ADMIN", "MANAGER")),
) -> DeviceRegisteredResponse:
    """Register a device for push notifications."""
    request.operation = "register_device"
    request.patient_id = patient_id
    command = Command(data=request)
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(result.error),
        )

    return result.data


@router.delete(
    "/{patient_id}/devices/{device_id}",
    response_model=DeviceRemovedResponse,
    summary="Remove a registered device",
)
async def remove_device(
    patient_id: str,
    device_id: str,
    use_case: DeviceRegistrationUseCase = Depends(get_device_registration_use_case),
    _=Depends(require_role("RECEPTION", "ADMIN", "MANAGER")),
) -> DeviceRemovedResponse:
    """Remove a registered device for a patient."""
    command = Command(data={
        "operation": "remove_device",
        "patient_id": patient_id,
        "device_id": device_id,
    })
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(result.error),
        )

    return result.data


# =============================================================================
# Notification Preferences
# =============================================================================


@router.patch(
    "/{patient_id}/preferences",
    response_model=NotificationPreferencesResponse,
    summary="Update notification preferences",
)
async def update_notification_preferences(
    patient_id: str,
    request: UpdateNotificationPreferencesRequest,
    use_case: DeviceRegistrationUseCase = Depends(get_device_registration_use_case),
    _=Depends(require_role("RECEPTION", "ADMIN", "MANAGER")),
) -> NotificationPreferencesResponse:
    """Update notification channel preferences (push, sound, vibration, etc.)."""
    request.operation = "update_preferences"
    request.patient_id = patient_id
    command = Command(data=request)
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(result.error),
        )

    return result.data


# =============================================================================
# Visit Tracking
# =============================================================================


@router.post(
    "/{patient_id}/visit",
    response_model=VisitRecordResponse,
    summary="Record a patient visit",
)
async def record_visit(
    patient_id: str,
    use_case: VisitTrackingUseCase = Depends(get_visit_tracking_use_case),
    _=Depends(require_role("RECEPTION", "ADMIN", "MANAGER", "DOCTOR")),
) -> VisitRecordResponse:
    """Record a new visit for the patient (increments counter)."""
    command = Command(data={
        "operation": "record_visit",
        "patient_id": patient_id,
    })
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(result.error),
        )

    return result.data


@router.get(
    "/{patient_id}/timeline",
    response_model=TimelineResponse,
    summary="Get patient timeline / visit history",
)
async def get_patient_timeline(
    patient_id: str,
    use_case: VisitTrackingUseCase = Depends(get_visit_tracking_use_case),
    _=Depends(require_role("RECEPTION", "ADMIN", "MANAGER", "DOCTOR", "NURSE")),
) -> TimelineResponse:
    """Get patient timeline with visit count, last visit, etc."""
    cqrs_query = CQRSQuery(data={
        "operation": "get_timeline",
        "patient_id": patient_id,
    })
    result = await use_case.run(cqrs_query)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(result.error),
        )

    return result.data


# =============================================================================
# Medical History
# =============================================================================


@router.post(
    "/{patient_id}/history",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Add medical history entry",
)
async def add_medical_history(
    patient_id: str,
    request: AddMedicalHistoryRequest,
    use_case: MedicalHistoryUseCase = Depends(get_medical_history_use_case),
    _=Depends(require_role("DOCTOR", "ADMIN")),
) -> dict:
    """Add a medical history entry for a patient."""
    request.operation = "add"
    request.patient_id = patient_id
    command = Command(data=request)
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(result.error),
        )

    return result.data


@router.get(
    "/{patient_id}/history",
    response_model=MedicalHistoryResponse,
    summary="List medical history",
)
async def list_medical_history(
    patient_id: str,
    use_case: MedicalHistoryUseCase = Depends(get_medical_history_use_case),
    _=Depends(require_role("DOCTOR", "ADMIN", "NURSE")),
) -> MedicalHistoryResponse:
    """List all medical history entries for a patient."""
    cqrs_query = CQRSQuery(data={
        "operation": "list",
        "patient_id": patient_id,
    })
    result = await use_case.run(cqrs_query)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(result.error),
        )

    return result.data


# =============================================================================
# Inquiry (Patient PWA → Reception)
# =============================================================================


@router.post(
    "/{patient_id}/inquiry",
    response_model=InquiryResponse,
    summary="Send an inquiry to reception (from PWA)",
)
async def send_inquiry(
    patient_id: str,
    request: SetInquiryRequest,
    use_case: UpdatePatientUseCase = Depends(get_update_patient_use_case),
) -> InquiryResponse:
    """Send an inquiry to reception (patient-facing endpoint, no auth required)."""
    request.operation = "set_inquiry"
    request.patient_id = patient_id
    command = Command(data=request)
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(result.error),
        )

    return result.data


@router.delete(
    "/{patient_id}/inquiry",
    response_model=InquiryResponse,
    summary="Clear patient inquiry (staff responded)",
)
async def clear_inquiry(
    patient_id: str,
    use_case: UpdatePatientUseCase = Depends(get_update_patient_use_case),
    _=Depends(require_role("RECEPTION", "ADMIN", "MANAGER")),
) -> InquiryResponse:
    """Clear the current reception inquiry (staff has responded)."""
    command = Command(data={
        "operation": "clear_inquiry",
        "patient_id": patient_id,
    })
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(result.error),
        )

    return result.data
