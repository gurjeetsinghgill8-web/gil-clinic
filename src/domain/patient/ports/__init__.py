"""Port interfaces (Protocols) for infrastructure adapters.

Ports are defined in the domain layer and implemented in the infrastructure layer.
This enables dependency inversion — domain never depends on infrastructure.
"""

from src.domain.patient.ports.patient_repository import PatientRepository
from src.domain.patient.ports.qr_code_generator import QRCodeGenerator
from src.domain.patient.ports.patient_notifier import PatientNotifier
from src.domain.patient.ports.patient_id_generator import PatientIdGenerator

__all__ = [
    "PatientRepository",
    "QRCodeGenerator",
    "PatientNotifier",
    "PatientIdGenerator",
]
