"""Patient Notifier port for the Patient Engine.

Defines the contract for sending notifications to patients.
Implemented by infrastructure layer (push, SMS, WhatsApp, email adapters).
"""

from __future__ import annotations

from typing import Protocol


class PatientNotifier(Protocol):
    """Interface for sending notifications to patients.

    Domain layer defines this protocol. Infrastructure provides the implementation
    for each channel (push, SMS, WhatsApp, email).
    """

    async def notify_status_update(
        self,
        patient_id: str,
        patient_name: str,
        device_tokens: list[str],
        test_name: str,
        new_status: str,
        room: str | None = None,
        token_number: int | None = None,
    ) -> dict[str, bool]:
        """Notify a patient about a test status update via push.

        Args:
            patient_id: Human-readable patient ID.
            patient_name: Patient's name for the notification message.
            device_tokens: List of push notification tokens.
            test_name: Name of the test (e.g., 'ECG').
            new_status: New status value (e.g., 'called', 'completed').
            room: Room number if applicable.
            token_number: Token number for the test.

        Returns:
            Dict mapping channel -> success bool.
        """
        ...

    async def notify_inquiry_response(
        self,
        patient_id: str,
        patient_name: str,
        device_tokens: list[str],
        response_text: str,
    ) -> bool:
        """Notify a patient that their inquiry was answered.

        Args:
            patient_id: Human-readable patient ID.
            patient_name: Patient's name.
            device_tokens: List of push notification tokens.
            response_text: The staff's response.

        Returns:
            True if notification was sent successfully.
        """
        ...

    async def notify_report_ready(
        self,
        patient_id: str,
        patient_name: str,
        device_tokens: list[str],
        test_name: str,
    ) -> bool:
        """Notify a patient that their report is ready.

        Args:
            patient_id: Human-readable patient ID.
            patient_name: Patient's name.
            device_tokens: List of push notification tokens.
            test_name: Name of the test.

        Returns:
            True if notification was sent successfully.
        """
        ...
