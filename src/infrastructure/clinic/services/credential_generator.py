"""Credential Generator — auto-generates secure credentials for new clinics.

Generates:
- clinic_code: CLINIC-XXX (sequential)
- clinic_username: DOCT-CLINIC-XXX (doctor initials + clinic code)
- clinic_password: 8-char random alphanumeric
- doctor_opd_pin: 4-digit random PIN
- dietician_pin: 4-digit random PIN
- staff_default_pin: "1234" (fixed default)
"""

from __future__ import annotations

import secrets
import string


def generate_clinic_code(clinic_count: int) -> str:
    """Generate sequential clinic code.

    Args:
        clinic_count: Current total number of clinics.

    Returns:
        e.g., "CLINIC-001", "CLINIC-050"
    """
    return f"CLINIC-{clinic_count + 1:03d}"


def generate_username(doctor_name: str, clinic_code: str) -> str:
    """Generate a unique username from doctor name and clinic code.

    Takes first 4 letters of doctor name + clinic code.
    Falls back to 'DOC' prefix if name is too short.

    Args:
        doctor_name: Full doctor name (e.g., "Gurjeet Singh")
        clinic_code: Generated clinic code (e.g., "CLINIC-001")

    Returns:
        e.g., "GURJ-CLINIC-001"
    """
    # Take first word, first 4 chars, uppercase
    first_name = doctor_name.strip().split()[0] if doctor_name.strip() else "DOC"
    prefix = first_name[:4].upper()
    if len(prefix) < 3:
        prefix = "DOC"
    return f"{prefix}-{clinic_code}"


def generate_password(length: int = 8) -> str:
    """Generate a random alphanumeric password.

    Uses mixed case letters + digits. No special chars for easy typing.

    Args:
        length: Password length (default 8).

    Returns:
        Random password string.
    """
    alphabet = string.ascii_letters + string.digits
    # Ensure at least one lowercase, one uppercase, one digit
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
        ):
            return password


def generate_pin(length: int = 4) -> str:
    """Generate a random numeric PIN.

    Args:
        length: PIN length (default 4).

    Returns:
        Random PIN string (e.g., "8472").
    """
    return "".join(secrets.choice(string.digits) for _ in range(length))


def generate_all_credentials(doctor_name: str, clinic_count: int) -> dict:
    """Generate all credentials for a new clinic in one call.

    Args:
        doctor_name: Doctor's full name.
        clinic_count: Current count of clinics (for sequential code).

    Returns:
        Dict with all generated credentials.
    """
    clinic_code = generate_clinic_code(clinic_count)
    username = generate_username(doctor_name, clinic_code)
    password = generate_password(8)
    opd_pin = generate_pin(4)
    dietician_pin = generate_pin(4)

    return {
        "clinic_code": clinic_code,
        "clinic_username": username,
        "clinic_password": password,
        "doctor_opd_pin": opd_pin,
        "dietician_pin": dietician_pin,
        "staff_default_pin": "1234",
    }
