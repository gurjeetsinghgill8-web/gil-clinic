"""Authentication domain service — pure domain rules only.

According to Clean Architecture, the Domain Layer contains business rules only.
All orchestration (repository calls, event publishing, transaction management)
lives in the Application Layer use cases.

This service has been stripped of all orchestration. It now contains only
the domain-level coordination that doesn't naturally belong in a single entity:

- PIN format validation
- OTP format validation
- Session limit calculations
- Role hierarchy evaluation for authorization

Domain rules:
- Identity publishes events only — never makes direct calls to other engines
- Domain depends on nothing outside src/domain/
- All side effects go through Application Layer use cases
"""

from __future__ import annotations

import re


class AuthenticationDomainService:
    """Domain service for authentication rules.

    This service is PURE DOMAIN — it contains only business rules that
    coordinate across multiple entities/value objects. It does NOT:

    - Call repositories (that's Application Layer)
    - Create sessions or tokens (that's Application Layer)
    - Publish events (that's Application Layer)
    - Manage transactions (that's Application Layer)

    What it DOES contain:
    - PIN format validation rules
    - OTP format validation rules
    - Cross-aggregate rule evaluation
    """

    PIN_PATTERN: re.Pattern = re.compile(r"^\d{4,6}$")
    OTP_PATTERN: re.Pattern = re.compile(r"^\d{6}$")

    def validate_pin_format(self, pin: str) -> tuple[bool, str | None]:
        """Validate that a PIN meets format requirements.

        Rules:
        - 4-6 digits
        - Numeric only

        Args:
            pin: The PIN to validate.

        Returns:
            Tuple of (is_valid: bool, error_message: str | None).
        """
        if not pin:
            return (False, "PIN is required. PIN dena zaroori hai.")
        if not self.PIN_PATTERN.match(pin):
            return (
                False,
                "PIN must be 4-6 numeric digits. PIN 4-6 digits ka hona chahiye.",
            )
        return (True, None)

    def validate_otp_format(self, otp: str) -> tuple[bool, str | None]:
        """Validate that an OTP meets format requirements.

        Rules:
        - 6 digits
        - Numeric only

        Args:
            otp: The OTP to validate.

        Returns:
            Tuple of (is_valid: bool, error_message: str | None).
        """
        if not otp:
            return (False, "OTP is required.")
        if not self.OTP_PATTERN.match(otp):
            return (False, "OTP must be exactly 6 digits.")
        return (True, None)

    def can_role_manage_role(
        self, actor_hierarchy_level: int, target_hierarchy_level: int
    ) -> tuple[bool, str | None]:
        """Check if a role with the given hierarchy can manage another role.

        A role can manage another only if its hierarchy level is strictly higher.

        Args:
            actor_hierarchy_level: Hierarchy level of the acting role.
            target_hierarchy_level: Hierarchy level of the target role.

        Returns:
            Tuple of (allowed: bool, reason: str | None).
        """
        if actor_hierarchy_level <= target_hierarchy_level:
            return (
                False,
                "Insufficient role hierarchy. "
                "Aapke role ki hierarchy kaafi nahi hai.",
            )
        return (True, None)

    def get_session_limit_info(
        self, active_session_count: int, max_sessions: int = 10
    ) -> dict:
        """Evaluate session limit status.

        Args:
            active_session_count: Current active sessions.
            max_sessions: Maximum allowed sessions.

        Returns:
            Dict with can_create, current, max, and message.
        """
        can_create = active_session_count < max_sessions
        return {
            "can_create": can_create,
            "current": active_session_count,
            "max": max_sessions,
            "message": (
                None
                if can_create
                else f"Maximum {max_sessions} active sessions reached. "
                f"Please revoke another session first."
            ),
        }

    def __repr__(self) -> str:
        return "<AuthenticationDomainService>"
