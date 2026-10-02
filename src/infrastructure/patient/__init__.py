"""Patient Engine infrastructure package.

Contains SQLAlchemy models, service implementations, and event handling.
"""

from src.infrastructure.patient.models import PatientModel
from src.infrastructure.patient.services.patient_id_generator import (
    PatientIdGeneratorService,
)
from src.infrastructure.patient.services.qr_code_generator import (
    PatientQRCodeGenerator,
)
from src.infrastructure.patient.events.event_serializer import (
    PatientEventSerializer,
)
from src.infrastructure.patient.config.settings import (
    PATIENT_QR_EXPIRY_HOURS,
    PATIENT_INACTIVITY_DAYS,
    MAX_DEVICES_PER_PATIENT,
    PATIENT_ID_PREFIX,
)

__all__ = [
    "PatientModel",
    "PatientIdGeneratorService",
    "PatientQRCodeGenerator",
    "PatientEventSerializer",
    "PATIENT_QR_EXPIRY_HOURS",
    "PATIENT_INACTIVITY_DAYS",
    "MAX_DEVICES_PER_PATIENT",
    "PATIENT_ID_PREFIX",
]
