"""Specifications for Patient queries.

Uses the same Specification pattern as the Identity Engine.
"""

from __future__ import annotations

from sqlalchemy import and_, or_
from sqlalchemy.sql import ColumnElement

from src.infrastructure.persistence.identity.specifications.base_specification import (
    Specification,
)
from src.infrastructure.patient.models.patient_model import PatientModel


class ByPatientIdSpecification(Specification):
    """Filter by human-readable patient ID."""

    def __init__(self, patient_id: str) -> None:
        self._patient_id = patient_id

    def apply(self) -> ColumnElement:
        return PatientModel.patient_id == self._patient_id


class ByPhoneHashSpecification(Specification):
    """Filter by phone hash."""

    def __init__(self, phone_hash: str) -> None:
        self._phone_hash = phone_hash

    def apply(self) -> ColumnElement:
        return PatientModel.phone_hash == self._phone_hash


class ByQrHashSpecification(Specification):
    """Filter by QR identity hash."""

    def __init__(self, qr_hash: str) -> None:
        self._qr_hash = qr_hash

    def apply(self) -> ColumnElement:
        return PatientModel.qr_hash == self._qr_hash


class ByStatusSpecification(Specification):
    """Filter by lifecycle status."""

    def __init__(self, status: str) -> None:
        self._status = status

    def apply(self) -> ColumnElement:
        return PatientModel.status == self._status


class ActivePatientsSpecification(Specification):
    """Filter for active patients only."""

    def apply(self) -> ColumnElement:
        return PatientModel.status.in_(["active", "inactive"])


class NameSearchSpecification(Specification):
    """Search by name using ILIKE."""

    def __init__(self, query: str) -> None:
        self._query = query

    def apply(self) -> ColumnElement:
        search_pattern = f"%{self._query}%"
        return PatientModel.name.ilike(search_pattern)


class NotMergedSpecification(Specification):
    """Exclude merged patient records."""

    def apply(self) -> ColumnElement:
        return PatientModel.merged_into_patient_id.is_(None)
