"""DeviceRegistrationUseCase — manage patient device registrations for PWA.

Supports:
1. Register a device for push notifications
2. Remove a device
3. Update notification preferences

Dependencies:
- PatientRepository, EventPublisher
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import (
    NotFoundError,
    ValidationError,
)
from src.application.patient.dtos.responses import (
    RegisterDeviceRequest,
    DeviceRegisteredResponse,
    DeviceRemovedResponse,
    UpdateNotificationPreferencesRequest,
    NotificationPreferencesResponse,
)
from src.domain.patient.value_objects.device_registration import (
    DeviceRegistration,
)
from src.domain.patient.value_objects.notification_preference import (
    NotificationPreference,
)
from src.domain.patient.events.patient_events import (
    patient_device_registered,
    patient_device_removed,
    patient_notification_preferences_updated,
)

if TYPE_CHECKING:
    from src.domain.patient.ports.patient_repository import PatientRepository
    from src.domain.identity.ports.event_publisher import EventPublisher


class DeviceRegistrationUseCase(BaseUseCase):
    """Use case for managing patient device registrations."""

    def __init__(
        self,
        patient_repo: PatientRepository,
        event_publisher: EventPublisher,
    ) -> None:
        super().__init__()
        self._patient_repo = patient_repo
        self._event_publisher = event_publisher

    async def authorize(self, command: Command) -> None:
        """Device registration from patient PWA uses QR auth or staff route."""
        pass

    async def execute(self, command: Command) -> Result:
        """Execute device registration operation.

        Args:
            command: Command with operation type and parameters.

        Returns:
            Result with appropriate response.
        """
        dto = command.data
        operation = getattr(dto, "operation", "register")

        try:
            if operation == "register_device":
                return await self._register_device(dto)
            elif operation == "remove_device":
                return await self._remove_device(dto)
            elif operation == "update_preferences":
                return await self._update_preferences(dto)
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

    async def _register_device(self, dto: RegisterDeviceRequest) -> Result:
        """Register a device for push notifications."""
        patient = await self._patient_repo.get_by_patient_id(dto.patient_id)
        if not patient:
            raise NotFoundError(
                message=f"Patient with ID '{dto.patient_id}' not found.",
                details={"patient_id": dto.patient_id},
            )

        device = DeviceRegistration.register(
            device_id=dto.device_id,
            device_name=dto.device_name,
            push_token=dto.push_token,
            platform=dto.platform,
            user_agent=dto.user_agent,
            ip_address=dto.ip_address,
        )
        patient.register_device(device)
        await self._patient_repo.save(patient)

        self._event_publisher.publish(
            patient_device_registered(
                patient_id=str(patient.id),
                device_id=dto.device_id,
                platform=dto.platform,
            )
        )

        return Result.ok(
            data=DeviceRegisteredResponse(
                device_id=dto.device_id,
                message="Device registered for notifications.",
            ),
        )

    async def _remove_device(self, dto: RegisterDeviceRequest) -> Result:
        """Remove a registered device."""
        patient_id = getattr(dto, "patient_id", None)
        if not patient_id:
            raise ValidationError(
                message="Patient ID is required.",
                details={"field": "patient_id"},
            )

        patient = await self._patient_repo.get_by_patient_id(patient_id)
        if not patient:
            raise NotFoundError(
                message=f"Patient with ID '{patient_id}' not found.",
                details={"patient_id": patient_id},
            )

        removed = patient.remove_device(dto.device_id)
        if not removed:
            raise NotFoundError(
                message=f"Device '{dto.device_id}' not found for this patient.",
                details={"device_id": dto.device_id},
            )

        await self._patient_repo.save(patient)

        self._event_publisher.publish(
            patient_device_removed(
                patient_id=str(patient.id),
                device_id=dto.device_id,
            )
        )

        return Result.ok(
            data=DeviceRemovedResponse(
                device_id=dto.device_id,
                message="Device removed successfully.",
            ),
        )

    async def _update_preferences(
        self, dto: UpdateNotificationPreferencesRequest
    ) -> Result:
        """Update notification preferences."""
        patient = await self._patient_repo.get_by_patient_id(dto.patient_id)
        if not patient:
            raise NotFoundError(
                message=f"Patient with ID '{dto.patient_id}' not found.",
                details={"patient_id": dto.patient_id},
            )

        current = patient.notification_preferences
        new_prefs = NotificationPreference(
            push_enabled=dto.push_enabled if dto.push_enabled is not None else current.push_enabled,
            sms_enabled=dto.sms_enabled if dto.sms_enabled is not None else current.sms_enabled,
            whatsapp_enabled=dto.whatsapp_enabled if dto.whatsapp_enabled is not None else current.whatsapp_enabled,
            email_enabled=dto.email_enabled if dto.email_enabled is not None else current.email_enabled,
            sound_enabled=dto.sound_enabled if dto.sound_enabled is not None else current.sound_enabled,
            vibration_enabled=dto.vibration_enabled if dto.vibration_enabled is not None else current.vibration_enabled,
        )

        patient.update_notification_preferences(new_prefs)
        await self._patient_repo.save(patient)

        # Determine enabled channels
        channels = []
        if new_prefs.push_enabled:
            channels.append("push")
        if new_prefs.sms_enabled:
            channels.append("sms")
        if new_prefs.whatsapp_enabled:
            channels.append("whatsapp")
        if new_prefs.email_enabled:
            channels.append("email")

        self._event_publisher.publish(
            patient_notification_preferences_updated(
                patient_id=str(patient.id),
                channels=channels,
            )
        )

        return Result.ok(
            data=NotificationPreferencesResponse(
                push_enabled=new_prefs.push_enabled,
                sms_enabled=new_prefs.sms_enabled,
                whatsapp_enabled=new_prefs.whatsapp_enabled,
                email_enabled=new_prefs.email_enabled,
                sound_enabled=new_prefs.sound_enabled,
                vibration_enabled=new_prefs.vibration_enabled,
            ),
            message="Notification preferences updated.",
        )
