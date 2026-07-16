"""Patient DTOs package."""

from src.application.patient.dtos.responses import (
    RegisterPatientRequest,
    UpdatePatientRequest,
    RegisterDeviceRequest,
    UpdateNotificationPreferencesRequest,
    AddMedicalHistoryRequest,
    SetInquiryRequest,
    BlockPatientRequest,
    MergePatientsRequest,
    SearchPatientsRequest,
    RegisterPatientResponse,
    PatientResponse,
    PatientListResponse,
    DeviceRegisteredResponse,
    DeviceRemovedResponse,
    NotificationPreferencesResponse,
    InquiryResponse,
    PatientStatusChangeResponse,
    MergeResponse,
    ErrorResponse,
    Gender,
    PatientStatusEnum,
)

__all__ = [
    # Requests
    "RegisterPatientRequest",
    "UpdatePatientRequest",
    "RegisterDeviceRequest",
    "UpdateNotificationPreferencesRequest",
    "AddMedicalHistoryRequest",
    "SetInquiryRequest",
    "BlockPatientRequest",
    "MergePatientsRequest",
    "SearchPatientsRequest",
    # Responses
    "RegisterPatientResponse",
    "PatientResponse",
    "PatientListResponse",
    "DeviceRegisteredResponse",
    "DeviceRemovedResponse",
    "NotificationPreferencesResponse",
    "InquiryResponse",
    "PatientStatusChangeResponse",
    "MergeResponse",
    "ErrorResponse",
    # Enums
    "Gender",
    "PatientStatusEnum",
]
