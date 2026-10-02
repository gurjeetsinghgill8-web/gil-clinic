"""User aggregate root for the Identity Engine.

The User is the central aggregate in the identity bounded context.
It manages:
- Authentication credentials (PIN, password)
- Account lockout state (5 failed attempts → 30 min lock)
- Role assignment
- Active/inactive status

User publishes events — it never calls other aggregates directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from src.shared.domain.base_entity import BaseEntity, uuid7

if TYPE_CHECKING:
    import uuid

    from src.domain.identity.entities.role import Role
    from src.domain.identity.value_objects.device_info import DeviceInfo
    from src.domain.identity.value_objects.lockout_result import LockoutResult


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_LOGIN_ATTEMPTS: int = 5
LOCKOUT_DURATION_MINUTES: int = 30
PIN_MIN_LENGTH: int = 4
PIN_MAX_LENGTH: int = 6


@dataclass
class User(BaseEntity):
    """Staff user aggregate root.

    Attributes:
        username: Unique login name.
        full_name: Display name (encrypted at rest).
        role_code: FK to Role.code.
        department: Optional department/unit.
        pin_hash: Bcrypt hash of the 4-6 digit PIN.
        phone: Encrypted phone number.
        phone_hash: SHA-256 hash for lookup.
        email: Encrypted email (optional).
        password_hash: Bcrypt hash of text password (admin only).
        login_attempts: Consecutive failed logins since last success.
        locked_until: If set, account is locked until this time.
        is_active: Soft-delete / deactivation flag.
        last_login: Timestamp of the most recent successful login.
    """

    username: str
    full_name: str
    role_code: str
    phone: str
    phone_hash: str
    department: str | None = None
    pin_hash: str | None = None
    email: str | None = None
    password_hash: str | None = None
    login_attempts: int = 0
    locked_until: datetime | None = None
    is_active: bool = True
    last_login: datetime | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        username: str,
        full_name: str,
        role_code: str,
        phone: str,
        phone_hash: str,
        department: str | None = None,
        email: str | None = None,
        pin_hash: str | None = None,
        password_hash: str | None = None,
    ) -> User:
        """Create a new User aggregate.

        Args:
            username: Unique login name.
            full_name: Display name.
            role_code: Must reference an existing Role.code.
            phone: Encrypted phone number.
            phone_hash: SHA-256 hash for lookups.
            department: Optional department name.
            email: Encrypted email (optional).
            pin_hash: Bcrypt hash of PIN (optional for admin).
            password_hash: Bcrypt hash of password (admin only).

        Returns:
            New User instance with default active state.
        """
        return cls(
            username=username,
            full_name=full_name,
            role_code=role_code,
            phone=phone,
            phone_hash=phone_hash,
            department=department,
            email=email,
            pin_hash=pin_hash,
            password_hash=password_hash,
        )

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def can_authenticate(self) -> None:
        """Check if the user is allowed to attempt authentication.

        Raises:
            AccountLockedError: If account is locked and lock hasn't expired.
            UserNotFoundError: If account is deactivated.
        """
        from src.domain.identity.exceptions.domain_error import (
            AccountLockedError,
            UserNotFoundError,
        )

        if not self.is_active:
            raise UserNotFoundError(
                details={"username": self.username, "reason": "Account deactivated"}
            )

        if self.locked_until and self.locked_until > datetime.now(timezone.utc):
            raise AccountLockedError(
                locked_until=self.locked_until.isoformat(),
                details={
                    "username": self.username,
                    "locked_until": self.locked_until.isoformat(),
                },
            )
        # Auto-expire lock if time has passed
        if self.locked_until and self.locked_until <= datetime.now(timezone.utc):
            self.locked_until = None
            self.login_attempts = 0

    def record_failed_attempt(self) -> LockoutResult | None:
        """Increment login attempts and lock account if threshold reached.

        Returns:
            LockoutResult if account was just locked, None otherwise.
        """
        from src.domain.identity.value_objects.lockout_result import LockoutResult

        self.login_attempts += 1
        self.touch()

        if self.login_attempts >= MAX_LOGIN_ATTEMPTS:
            lock_until = datetime.now(timezone.utc) + timedelta(
                minutes=LOCKOUT_DURATION_MINUTES
            )
            self.locked_until = lock_until
            return LockoutResult(
                locked=True,
                locked_until=lock_until,
                attempts=self.login_attempts,
            )
        return LockoutResult(
            locked=False,
            attempts=self.login_attempts,
            remaining=MAX_LOGIN_ATTEMPTS - self.login_attempts,
        )

    def record_successful_login(self) -> None:
        """Reset lockout state after a successful login."""
        self.login_attempts = 0
        self.locked_until = None
        self.last_login = datetime.now(timezone.utc)
        self.touch()

    # ------------------------------------------------------------------
    # PIN Management
    # ------------------------------------------------------------------

    def has_pin(self) -> bool:
        """Check if the user has a PIN set."""
        return self.pin_hash is not None

    def has_password(self) -> bool:
        """Check if the user has a password set (admin)."""
        return self.password_hash is not None

    def set_pin(self, pin_hash: str) -> None:
        """Set a new PIN hash.

        Args:
            pin_hash: Bcrypt hash of the new PIN.
        """
        self.pin_hash = pin_hash
        self.touch()

    def set_password(self, password_hash: str) -> None:
        """Set a new password hash.

        Args:
            password_hash: Bcrypt hash of the new password.
        """
        self.password_hash = password_hash
        self.touch()

    # ------------------------------------------------------------------
    # Account State
    # ------------------------------------------------------------------

    def disable(self, reason: str | None = None) -> None:
        """Deactivate the user account.

        Args:
            reason: Optional reason for deactivation.
        """
        self.is_active = False
        self.touch()

    def reactivate(self) -> None:
        """Reactivate a deactivated account.

        Also clears any remaining lockout state.
        """
        self.is_active = True
        self.login_attempts = 0
        self.locked_until = None
        self.touch()

    def unlock(self, unlocked_by: str = "system") -> None:
        """Manually unlock the account.

        Args:
            unlocked_by: Who initiated the unlock ("system" or user ID).
        """
        self.login_attempts = 0
        self.locked_until = None
        self.touch()

    def change_role(self, new_role_code: str) -> tuple[str, str]:
        """Change the user's role.

        Args:
            new_role_code: New role code to assign.

        Returns:
            Tuple of (old_role_code, new_role_code).
        """
        old_role = self.role_code
        self.role_code = new_role_code
        self.touch()
        return (old_role, new_role_code)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def is_locked(self) -> bool:
        """Check if the account is currently locked."""
        if not self.locked_until:
            return False
        if self.locked_until <= datetime.now(timezone.utc):
            return False
        return True

    @property
    def remaining_attempts(self) -> int:
        """Number of remaining attempts before lockout."""
        return max(0, MAX_LOGIN_ATTEMPTS - self.login_attempts)

    def __repr__(self) -> str:
        return (
            f"<User id={self.id} "
            f"username={self.username} "
            f"role={self.role_code} "
            f"active={self.is_active}>"
        )
