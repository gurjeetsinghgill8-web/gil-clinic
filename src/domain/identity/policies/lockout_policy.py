"""Lockout policy for the Identity Engine.

Encapsulates the business rules for account lockout:
- Max 5 failed login attempts
- 30-minute automatic lock duration
- Admin unlock capability
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.domain.identity.entities.user import User


class LockoutPolicy:
    """Policy for account lockout rules.

    This policy is stateless — it evaluates lockout conditions
    based on the current User state and returns decisions.
    """

    MAX_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 30

    def check_lockout(self, user: User) -> bool:
        """Check if the user should be locked out.

        Evaluates if the user has exceeded the max failed attempt count.

        Args:
            user: User aggregate to evaluate.

        Returns:
            True if the user should be locked out.
        """
        return user.login_attempts >= self.MAX_ATTEMPTS

    def is_locked(self, user: User) -> bool:
        """Check if the user is currently locked.

        Auto-expires the lock if the duration has passed.

        Args:
            user: User aggregate to check.

        Returns:
            True if still within lockout window.
        """
        if not user.locked_until:
            return False
        if user.locked_until <= datetime.now(timezone.utc):
            return False
        return True

    def get_lockout_end(self, user: User) -> datetime | None:
        """Get when the lockout ends.

        Args:
            user: Locked user.

        Returns:
            Lock expiry time, or None if not locked.
        """
        if not self.is_locked(user):
            return None
        return user.locked_until

    def get_remaining_attempts(self, user: User) -> int:
        """Get the number of remaining attempts before lockout.

        Args:
            user: User to check.

        Returns:
            Remaining attempts (0 if locked).
        """
        if self.is_locked(user):
            return 0
        return max(0, self.MAX_ATTEMPTS - user.login_attempts)

    def should_warn(self, user: User) -> bool:
        """Check if the user should be warned about remaining attempts.

        Warns when 2 or fewer attempts remain.

        Args:
            user: User to check.

        Returns:
            True if warning should be shown.
        """
        remaining = self.get_remaining_attempts(user)
        return 0 < remaining <= 2

    def can_auto_unlock(self, user: User) -> bool:
        """Check if the lockout period has auto-expired.

        Args:
            user: Locked user.

        Returns:
            True if lock period has passed and account can be auto-unlocked.
        """
        if not user.locked_until:
            return True
        return user.locked_until <= datetime.now(timezone.utc)

    def time_until_unlock(self, user: User) -> timedelta:
        """Get time remaining until automatic unlock.

        Args:
            user: Locked user.

        Returns:
            timedelta until unlock (0 if already unlocked).
        """
        if not user.locked_until:
            return timedelta()
        remaining = user.locked_until - datetime.now(timezone.utc)
        return max(remaining, timedelta())

    def __repr__(self) -> str:
        return (
            f"<LockoutPolicy "
            f"max_attempts={self.MAX_ATTEMPTS} "
            f"duration={self.LOCKOUT_DURATION_MINUTES}min>"
        )
