"""Bcrypt-based PIN hasher implementation.

Implements the PinHasher port protocol from the domain layer.
Uses bcrypt with configurable cost factor (default 12).

Usage:
    hasher = BcryptPinHasher()
    pin_hash = hasher.hash("1234")
    assert hasher.verify("1234", pin_hash) is True
"""

from __future__ import annotations

import bcrypt

from src.infrastructure.identity.config.settings import settings


class BcryptPinHasher:
    """PIN hasher using bcrypt with configurable cost.

    Implements the PinHasher protocol from domain.identity.ports.
    Thread-safe and stateless after construction.
    """

    def __init__(self, rounds: int | None = None) -> None:
        """Initialize the hasher.

        Args:
            rounds: bcrypt cost factor. Defaults to settings.BCRYPT_ROUNDS.
        """
        self._rounds = rounds or settings.BCRYPT_ROUNDS

    def hash(self, pin: str) -> str:
        """Hash a plaintext PIN with bcrypt.

        Args:
            pin: Plaintext PIN (4-6 digits).

        Returns:
            bcrypt hash string (includes embedded salt and cost).

        Raises:
            ValueError: If pin is empty.
        """
        if not pin:
            raise ValueError("PIN cannot be empty")
        hashed: bytes = bcrypt.hashpw(
            pin.encode("utf-8"),
            bcrypt.gensalt(rounds=self._rounds),
        )
        return hashed.decode("utf-8")

    def verify(self, pin: str, hashed: str) -> bool:
        """Verify a PIN against its bcrypt hash.

        Uses constant-time comparison (provided by bcrypt library).

        Args:
            pin: Plaintext PIN to verify.
            hashed: Previously generated bcrypt hash.

        Returns:
            True if PIN matches hash, False otherwise.
        """
        try:
            return bool(
                bcrypt.checkpw(
                    pin.encode("utf-8"),
                    hashed.encode("utf-8"),
                )
            )
        except (ValueError, AttributeError):
            return False
