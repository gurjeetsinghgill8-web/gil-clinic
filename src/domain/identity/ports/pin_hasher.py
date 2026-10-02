"""Port: PIN hashing interface.

Domain layer defines this protocol. Infrastructure provides BcryptPinHasher.
"""

from __future__ import annotations

from typing import Protocol


class PinHasher(Protocol):
    """Interface for PIN hashing and verification.

    Used by AuthenticationService to verify PINs during login.
    Implemented by BcryptPinHasher in the infrastructure layer.
    """

    def hash(self, pin: str) -> str:
        """Hash a plaintext PIN.

        Args:
            pin: Plaintext PIN (4-6 digits).

        Returns:
            Hashed PIN string (includes salt + cost).
        """
        ...

    def verify(self, pin: str, hashed: str) -> bool:
        """Verify a PIN against its hash.

        Args:
            pin: Plaintext PIN to verify.
            hashed: Previously hashed PIN.

        Returns:
            True if PIN matches hash, False otherwise.
        """
        ...
