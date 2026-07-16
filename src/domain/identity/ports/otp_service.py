"""Port: OTP generation and verification interface.

Domain layer defines this protocol. Infrastructure provides OtpGeneratorService.
"""

from __future__ import annotations

from typing import Protocol


class OtpService(Protocol):
    """Interface for one-time password operations.

    OTPs are 6-digit codes, valid for 5 minutes.
    Stored as SHA-256 hashes (never plaintext).
    """

    def generate(self) -> str:
        """Generate a cryptographically secure OTP.

        Returns:
            6-digit numeric OTP string.
        """
        ...

    def hash_otp(self, otp: str) -> str:
        """Hash an OTP for secure storage.

        Args:
            otp: Plaintext OTP string.

        Returns:
            SHA-256 hex digest.
        """
        ...

    def verify(self, otp: str, code_hash: str) -> bool:
        """Verify an OTP against its stored hash.

        Uses constant-time comparison to prevent timing attacks.

        Args:
            otp: Plaintext OTP to verify.
            code_hash: Stored SHA-256 hash.

        Returns:
            True if OTP matches, False otherwise.
        """
        ...
