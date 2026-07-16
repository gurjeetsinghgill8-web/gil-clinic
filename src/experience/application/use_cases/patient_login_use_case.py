"""Experience Engine — Patient Login Use Case.

Handles patient authentication via:
1. Phone number + OTP
2. QR code scan (payload contains patient reference)
3. Direct patient_id lookup (from token slip)

Returns a short-lived session token for subsequent /me, /my-status calls.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import NotFoundError, ValidationError

if TYPE_CHECKING:
    from src.domain.patient.ports.patient_repository import PatientRepository
    from src.infrastructure.patient.services.qr_code_generator import (
        PatientQRCodeGenerator,
    )


# In-memory session store (temporary — replace with Redis in production)
_patient_sessions: dict[str, dict[str, Any]] = {}
SESSION_EXPIRY_MINUTES = 60


class PatientLoginUseCase(BaseUseCase):
    """Use case for patient login via phone, QR, or patient_id.

    Creates a short-lived session token for the Experience API.
    """

    def __init__(
        self,
        patient_repo: PatientRepository,
        qr_code_generator: PatientQRCodeGenerator | None = None,
    ) -> None:
        super().__init__()
        self._patient_repo = patient_repo
        self._qr_code_generator = qr_code_generator

    async def authorize(self, command: Command) -> None:
        """Patient login is a public endpoint."""
        pass

    async def execute(self, command: Command) -> Result:
        """Execute patient login.

        Args:
            command: Command with login method and credentials.

        Returns:
            Result with session token and patient info.
        """
        dto = command.data
        method = dto.get("method", "phone")

        try:
            patient = None

            if method == "phone":
                phone = dto.get("phone", "")
                if not phone or not phone.isdigit() or len(phone) != 10:
                    raise ValidationError(
                        message="Valid 10-digit phone number is required.",
                        details={"field": "phone"},
                    )
                phone_hash = hashlib.sha256(phone.encode()).hexdigest()
                patient = await self._patient_repo.get_by_phone_hash(phone_hash)

            elif method == "qr":
                qr_payload = dto.get("qr_payload", "")
                if not qr_payload or not self._qr_code_generator:
                    raise ValidationError(
                        message="QR payload is required.",
                        details={"field": "qr_payload"},
                    )
                patient_id = await self._qr_code_generator.verify_qr_scan(qr_payload)
                if not patient_id:
                    raise ValidationError(
                        message="Invalid or expired QR code.",
                        details={"field": "qr_payload"},
                    )
                patient = await self._patient_repo.get_by_patient_id(patient_id)

            elif method == "patient_id":
                pid = dto.get("patient_id", "")
                if not pid:
                    raise ValidationError(
                        message="Patient ID is required.",
                        details={"field": "patient_id"},
                    )
                patient = await self._patient_repo.get_by_patient_id(pid)

            else:
                raise ValidationError(
                    message=f"Unknown login method: {method}",
                    details={"method": method},
                )

            if not patient:
                raise NotFoundError(
                    message="Patient not found. Please check your details.",
                    details={"method": method},
                )

            if not patient.can_register_visit and patient.status.status.value != "active":
                # Allow login for inactive patients, block blocked/merged
                if patient.status.status.value in ("blocked", "merged"):
                    raise ValidationError(
                        message=f"Patient account is {patient.status.status.value}. Contact reception.",
                        details={"status": patient.status.status.value},
                    )

            # Create session token
            session_token = secrets.token_hex(32)
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=SESSION_EXPIRY_MINUTES)

            _patient_sessions[session_token] = {
                "patient_uuid": str(patient.id),
                "patient_id": patient.patient_id,
                "phone_hash": patient.contact.phone_hash,
                "created_at": datetime.now(timezone.utc),
                "expires_at": expires_at,
            }

            return Result.ok(
                data={
                    "session_token": session_token,
                    "expires_at": expires_at.isoformat(),
                    "patient": {
                        "patient_id": patient.patient_id,
                        "name": patient.demographics.name,
                        "phone": patient.contact.phone[-4:],  # last 4 digits only
                        "age": patient.demographics.age,
                        "gender": patient.demographics.gender,
                        "has_active_tests": False,  # Will be populated by status query
                    },
                },
                message=f"Welcome, {patient.demographics.name}!",
            )

        except (NotFoundError, ValidationError) as exc:
            return Result.fail(
                error=str(exc),
                code=exc.code,
                details=exc.details,
            )


def get_patient_from_session(session_token: str) -> dict[str, Any] | None:
    """Get patient context from a session token.

    Args:
        session_token: The session token from login.

    Returns:
        Patient session data dict, or None if invalid/expired.
    """
    session = _patient_sessions.get(session_token)
    if not session:
        return None

    if datetime.now(timezone.utc) > session["expires_at"]:
        del _patient_sessions[session_token]
        return None

    return session


def refresh_session(session_token: str) -> bool:
    """Extend session expiry.

    Args:
        session_token: The session token to refresh.

    Returns:
        True if refreshed, False if invalid.
    """
    session = _patient_sessions.get(session_token)
    if not session:
        return False
    session["expires_at"] = datetime.now(timezone.utc) + timedelta(minutes=SESSION_EXPIRY_MINUTES)
    return True
