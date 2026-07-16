"""QR Code Generator port for the Patient Engine.

Defines the contract for generating QR identities.
Implemented by infrastructure layer (e.g., using qrcode[pil] library).
"""

from __future__ import annotations

from typing import Protocol

from src.domain.patient.value_objects.qr_identity import QRIdentity


class QRCodeGenerator(Protocol):
    """Interface for QR code generation.

    Domain layer defines this protocol. Infrastructure provides the implementation.
    """

    async def generate_patient_qr(
        self,
        patient_id: str,
        patient_uuid: str,
        expiry_hours: int | None = 72,
    ) -> QRIdentity:
        """Generate a QR identity for a patient.

        The QR payload contains the patient_id, a random salt, and expiry.
        The payload is encrypted and hashed for lookup.

        Args:
            patient_id: Human-readable patient ID.
            patient_uuid: Internal UUID of the patient.
            expiry_hours: How long the QR code is valid (default 72h).

        Returns:
            A QRIdentity value object.
        """
        ...

    async def verify_qr_scan(self, qr_payload: str) -> str | None:
        """Verify a scanned QR payload and return the patient_id if valid.

        Decrypts the payload, checks expiry, returns the patient_id.

        Args:
            qr_payload: The encrypted QR payload scanned from the QR code.

        Returns:
            Patient ID if valid, None if expired or tampered.
        """
        ...
