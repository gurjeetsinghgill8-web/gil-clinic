"""OTP generator service implementation.

Implements the OtpService port protocol from the domain layer.
Generates cryptographically secure 6-digit OTPs and provides
SHA-256 hashing with constant-time verification.

Usage:
    service = OtpGeneratorService()
    otp = service.generate()  # "837291"
    hashed = service.hash_otp(otp)
    assert service.verify(otp, hashed) is True
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from src.infrastructure.identity.config.settings import settings


class OtpGeneratorService:
    """Cryptographically secure OTP generator.

    Implements the OtpService protocol from domain.identity.ports.
    Thread-safe and stateless.

    Generates 6-digit numeric OTPs using secrets.randbelow().
    Stores OTPs as SHA-256 hashes (never plaintext).
    Verification uses HMAC comparison for timing-attack resistance.
    """

    def __init__(self, length: int | None = None) -> None:
        """Initialize the OTP service.

        Args:
            length: Number of OTP digits. Defaults to settings.OTP_LENGTH.
        """
        self._length = length or settings.OTP_LENGTH

    def generate(self) -> str:
        """Generate a cryptographically secure OTP.

        Uses secrets.randbelow() which is backed by the OS CSPRNG.

        Returns:
            N-digit numeric OTP string (padded with leading zeros).
        """
        # Generate a random integer with the correct number of digits
        # e.g., for 6 digits: range 0 to 999999
        max_value = 10**self._length
        otp_int = secrets.randbelow(max_value)
        # Pad with leading zeros to ensure consistent length
        return str(otp_int).zfill(self._length)

    def hash_otp(self, otp: str) -> str:
        """Hash an OTP for secure storage using SHA-256.

        Args:
            otp: Plaintext OTP string.

        Returns:
            SHA-256 hex digest.
        """
        return hashlib.sha256(otp.encode("utf-8")).hexdigest()

    def verify(self, otp: str, code_hash: str) -> bool:
        """Verify an OTP against its stored hash.

        Uses HMAC comparison (constant-time) to prevent timing attacks.

        Args:
            otp: Plaintext OTP to verify.
            code_hash: Stored SHA-256 hash.

        Returns:
            True if OTP matches hash, False otherwise.
        """
        computed = self.hash_otp(otp)
        # hmac.compare_digest is constant-time
        return hmac.compare_digest(computed, code_hash)
