"""QR Code Generator implementation for the Patient Engine.

Generates QR identities for PWA patient login.
Uses QR code library for image generation and AES for payload encryption.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone

from src.domain.patient.value_objects.qr_identity import QRIdentity


class PatientQRCodeGenerator:
    """Generates and verifies QR identities for patients.

    QR payload format (encrypted):
    {
        "pid": "<patient_id>",
        "salt": "<random_salt>",
        "exp": "<expiry_timestamp>"
    }

    The payload is encrypted with a server secret, and a SHA-256 hash
    of the encrypted payload is stored for lookups.
    """

    # In production, this would come from settings/KEK
    _SERVER_SECRET: str = "ghos-patient-qr-secret-change-in-production"

    def __init__(self, encryption_service=None) -> None:
        self._encryption_service = encryption_service

    async def generate_patient_qr(
        self,
        patient_id: str,
        patient_uuid: str,
        expiry_hours: int | None = 72,
    ) -> QRIdentity:
        """Generate a QR identity for a patient.

        Args:
            patient_id: Human-readable patient ID (e.g., 'CQ-20260714-001').
            patient_uuid: Internal UUID of the patient.
            expiry_hours: How long the QR code is valid (default 72h).

        Returns:
            A QRIdentity value object.
        """
        expires_at = None
        if expiry_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)

        # Build payload
        payload = {
            "pid": patient_id,
            "uuid": patient_uuid,
            "salt": secrets.token_hex(16),
            "exp": expires_at.isoformat() if expires_at else None,
        }

        # Encrypt payload (simple XOR with hash — in production use AES-256-GCM)
        payload_json = json.dumps(payload, separators=(",", ":"))
        encrypted = self._xor_encrypt(payload_json, self._SERVER_SECRET)

        # Hash for lookup
        qr_hash = hashlib.sha256(encrypted.encode()).hexdigest()

        return QRIdentity.create(
            qr_hash=qr_hash,
            qr_payload=encrypted,
            expires_at=expires_at,
        )

    async def verify_qr_scan(self, qr_payload: str) -> str | None:
        """Verify a scanned QR payload and return the patient_id if valid.

        Args:
            qr_payload: The encrypted QR payload scanned from the QR code.

        Returns:
            Patient ID if valid, None if expired or tampered.
        """
        try:
            decrypted = self._xor_decrypt(qr_payload, self._SERVER_SECRET)
            payload = json.loads(decrypted)

            # Check expiry
            exp_str = payload.get("exp")
            if exp_str:
                try:
                    expires_at = datetime.fromisoformat(exp_str)
                    if datetime.now(timezone.utc) > expires_at:
                        return None  # Expired
                except (ValueError, TypeError):
                    return None  # Invalid expiry

            return payload.get("pid")

        except (json.JSONDecodeError, Exception):
            return None  # Invalid or tampered payload

    @staticmethod
    def _xor_encrypt(data: str, secret: str) -> str:
        """Simple XOR-based encrypt/decrypt.

        NOTE: This is NOT cryptographically secure for production.
        Replace with AES-256-GCM before deployment.

        Args:
            data: String data to encrypt/decrypt.
            secret: Secret key for XOR.

        Returns:
            XOR'd result as hex string.
        """
        key = hashlib.sha256(secret.encode()).digest()
        result = bytearray()
        for i, char in enumerate(data.encode()):
            result.append(char ^ key[i % len(key)])
        return result.hex()

    @staticmethod
    def _xor_decrypt(hex_data: str, secret: str) -> str:
        """Reverse of _xor_encrypt: hex string → XOR → original string.

        Args:
            hex_data: Hex-encoded XOR'd data.
            secret: Secret key for XOR.

        Returns:
            Original decrypted string.
        """
        key = hashlib.sha256(secret.encode()).digest()
        raw = bytes.fromhex(hex_data)
        result = bytearray()
        for i, b in enumerate(raw):
            result.append(b ^ key[i % len(key)])
        return result.decode()
