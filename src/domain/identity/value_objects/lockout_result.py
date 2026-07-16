"""LockoutResult value object for the Identity Engine.

Returned from User.record_failed_attempt() to communicate
the result of a failed login attempt to the caller.
The caller uses this to decide whether to:
- Allow retry (locked=False, remaining > 0)
- Lock the account (locked=True)
- Warn about remaining attempts
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING


@dataclass(frozen=True)
class LockoutResult:
    """Immutable result of a failed login attempt.

    Attributes:
        locked: Whether the account is now locked.
        attempts: Total consecutive failed attempts.
        locked_until: If locked, when the lock expires.
        remaining: Number of remaining attempts before lockout.
    """

    locked: bool = False
    attempts: int = 0
    locked_until: datetime | None = None
    remaining: int = 5

    @property
    def should_warn(self) -> bool:
        """Check if the user should be warned about remaining attempts.

        Warns when 2 or fewer attempts remain.

        Returns:
            True if remaining <= 2.
        """
        return 0 < self.remaining <= 2

    @property
    def message(self) -> str:
        """Get a user-facing message for this lockout result.

        Returns:
            Appropriate message in English based on state.
        """
        if self.locked:
            until = self.locked_until.strftime("%H:%M UTC") if self.locked_until else "30 min"
            return f"Account locked until {until}. Too many failed attempts."
        if self.should_warn:
            return f"{self.remaining} attempt(s) remaining before lockout."
        return ""

    def __repr__(self) -> str:
        if self.locked:
            return f"<LockoutResult LOCKED until {self.locked_until}>"
        return f"<LockoutResult attempts={self.attempts} remaining={self.remaining}>"
