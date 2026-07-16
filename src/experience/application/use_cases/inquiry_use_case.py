"""Experience Engine — Inquiry Use Case.

Allows patients to send inquiries to reception ("Ask Reception")
and staff to respond / clear inquiries.

Delegates to Patient Engine for persistence.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import NotFoundError, ValidationError

if TYPE_CHECKING:
    from src.domain.patient.ports.patient_repository import PatientRepository


class PatientInquiryUseCase(BaseUseCase):
    """Use case for patient-reception communication."""

    def __init__(
        self,
        patient_repo: PatientRepository,
    ) -> None:
        super().__init__()
        self._patient_repo = patient_repo

    async def authorize(self, command: Command) -> None:
        pass

    async def execute(self, command: Command) -> Result:
        """Execute inquiry operation.

        Args:
            command: Command with operation type and data.

        Returns:
            Result with inquiry status.
        """
        dto = command.data
        operation = dto.get("operation", "send")
        patient_uuid = dto.get("patient_uuid", "")

        try:
            patient = await self._patient_repo.get_by_id(patient_uuid)
            if not patient:
                raise NotFoundError(
                    message="Patient not found.",
                )

            if operation == "send":
                inquiry_text = dto.get("inquiry_text", "").strip()
                if not inquiry_text:
                    raise ValidationError(
                        message="Inquiry text cannot be empty.",
                        details={"field": "inquiry_text"},
                    )
                patient.set_inquiry(inquiry_text)
                await self._patient_repo.save(patient)
                return Result.ok(
                    data={
                        "patient_id": patient.patient_id,
                        "inquiry_text": inquiry_text,
                        "status": "sent",
                    },
                    message="Your message has been sent to reception.",
                )

            elif operation == "clear":
                patient.clear_inquiry()
                await self._patient_repo.save(patient)
                return Result.ok(
                    data={
                        "patient_id": patient.patient_id,
                        "status": "cleared",
                    },
                    message="Inquiry cleared.",
                )

            elif operation == "get":
                return Result.ok(
                    data={
                        "patient_id": patient.patient_id,
                        "inquiry_text": patient.reception_inquiry,
                        "has_inquiry": patient.reception_inquiry is not None,
                    },
                )

            else:
                raise ValidationError(
                    message=f"Unknown operation: {operation}",
                    details={"operation": operation},
                )

        except (NotFoundError, ValidationError) as exc:
            return Result.fail(
                error=str(exc),
                code=exc.code,
                details=exc.details,
            )
