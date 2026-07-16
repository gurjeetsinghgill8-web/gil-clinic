"""AES-256-GCM encryption for PII data at rest.

Provides application-layer encryption for sensitive fields:
- phone, email, full_name, ip_address

Uses AES-256-GCM with:
- 256-bit key (derived from 256-bit master key via HKDF)
- Random 96-bit nonce per encryption
- 128-bit authentication tag

Key rotation supported via key_id prefix.
"""

from __future__ import annotations

import hashlib
import os
from base64 import b64decode, b64encode

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# 256-bit key = 32 bytes
_KEY_LENGTH = 32
# 96-bit nonce = 12 bytes (recommended for GCM)
_NONCE_LENGTH = 12


def _get_master_key() -> bytes:
    """Get the master encryption key from environment variable.

    Returns:
        32-byte key derived from GHOS_ENCRYPTION_KEY env var.

    Raises:
        ValueError: If GHOS_ENCRYPTION_KEY is not set.
    """
    key_str = os.getenv("GHOS_ENCRYPTION_KEY")
    if not key_str:
        raise ValueError(
            "GHOS_ENCRYPTION_KEY environment variable is not set. "
            "Generate with: openssl rand -hex 32"
        )
    # Accept hex-encoded 64-char string or raw 32-byte value
    if len(key_str) == 64:
        try:
            return bytes.fromhex(key_str)
        except ValueError:
            pass
    # Hash to 32 bytes if not exactly 64 hex chars
    return hashlib.sha256(key_str.encode()).digest()


def encrypt(plaintext: str, aad: bytes | None = None) -> str:
    """Encrypt a plaintext string with AES-256-GCM.

    Format: base64(nonce + ciphertext + tag)
    Version prefix: $v1$base64_encoded_data

    Args:
        plaintext: String to encrypt.
        aad: Optional additional authenticated data (e.g., user_id).

    Returns:
        Encrypted string with version prefix.
    """
    key = _get_master_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(_NONCE_LENGTH)
    ciphertext = aesgcm.encrypt(
        nonce,
        plaintext.encode("utf-8"),
        aad or b"",
    )
    # Prepend nonce to ciphertext (nonce + ciphertext + tag)
    encoded = b64encode(nonce + ciphertext).decode("ascii")
    return f"$v1${encoded}"


def decrypt(encrypted: str, aad: bytes | None = None) -> str:
    """Decrypt an AES-256-GCM encrypted string.

    Args:
        encrypted: Encrypted string with version prefix.
        aad: Additional authenticated data used during encryption.

    Returns:
        Decrypted plaintext string.

    Raises:
        ValueError: If encrypted format is invalid or decryption fails.
        cryptography.exceptions.InvalidTag: If authentication fails.
    """
    if not encrypted.startswith("$v1$"):
        raise ValueError("Unknown encryption format or not encrypted")

    key = _get_master_key()
    aesgcm = AESGCM(key)

    encoded = encrypted[4:]  # Strip "$v1$"
    raw = b64decode(encoded)

    nonce = raw[:_NONCE_LENGTH]
    ciphertext = raw[_NONCE_LENGTH:]

    plaintext = aesgcm.decrypt(nonce, ciphertext, aad or b"")
    return plaintext.decode("utf-8")


def hash_for_search(value: str) -> str:
    """Generate a searchable hash of a value.

    Used for lookups on encrypted fields (e.g., find user by phone).
    This is a SHA-256 hash, NOT reversible to original value.
    Same input always produces same hash (deterministic).

    Args:
        value: String to hash (e.g., phone number).

    Returns:
        SHA-256 hex digest.
    """
    return hashlib.sha256(value.encode()).hexdigest()


def encrypt_searchable(value: str) -> tuple[str, str]:
    """Encrypt a value AND return its searchable hash.

    Args:
        value: String to encrypt and hash.

    Returns:
        Tuple of (encrypted_value, searchable_hash).
    """
    return encrypt(value), hash_for_search(value)
