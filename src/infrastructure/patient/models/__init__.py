"""SQLAlchemy ORM models for patient tables.

Currently:
- patient.patients — Patient aggregate root
"""

from src.infrastructure.patient.models.patient_model import PatientModel

__all__ = [
    "PatientModel",
]
