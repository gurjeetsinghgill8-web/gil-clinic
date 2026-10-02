"""Session policy for the Identity Engine.

Encapsulates the business rules for session lifecycle:
- Max 10 concurrent sessions per user
- 24-hour default session duration
- Session can be extended
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.domain.identity.entities.session import Session


class SessionPolicy:
    """Policy for session lifecycle rules.

    This policy is stateless — it evaluates session conditions
    and returns decisions based on the current state.
    """

    MAX_CONCURRENT_SESSIONS: int = 10
    DEFAULT_DURATION_HOURS: int = 24
    MAX_DURATION_HOURS: int = 720  # 30 days

    def can_create_session(
        self, active_session_count: int
    ) -> tuple[bool, str | None]:
        """Check if a new session can be created.

        Args:
            active_session_count: Current active sessions for this user.

        Returns:
            Tuple of (allowed: bool, reason: str | None).
        """
        if active_session_count >= self.MAX_CONCURRENT_SESSIONS:
            return (
                False,
                f"Maximum {self.MAX_CONCURRENT_SESSIONS} concurrent sessions "
                f"allowed. Please revoke another session first.",
            )
        return (True, None)

    def is_near_expiry(self, session: Session, warning_minutes: int = 15) -> bool:
        """Check if a session is near expiry.

        Args:
            session: Session to check.
            warning_minutes: Threshold for "near expiry" warning.

        Returns:
            True if session expires within the warning window.
        """
        if not session.expires_at:
            return False
        remaining = session.expires_at - datetime.now(timezone.utc)
        return timedelta() < remaining <= timedelta(minutes=warning_minutes)

    def should_extend(self, session: Session) -> bool:
        """Check if a session should be auto-extended.

        Auto-extends if the session has been active within the last hour.

        Args:
            session: Session to check.

        Returns:
            True if the session should be extended.
        """
        if not session.last_activity:
            return False
        inactive_duration = datetime.now(timezone.utc) - session.last_activity
        return inactive_duration <= timedelta(hours=1)

    def validate_duration(self, hours: int) -> tuple[bool, str | None]:
        """Validate a session duration.

        Args:
            hours: Requested session duration in hours.

        Returns:
            Tuple of (valid: bool, error: str | None).
        """
        if hours < 1:
            return (False, "Session duration must be at least 1 hour.")
        if hours > self.MAX_DURATION_HOURS:
            return (
                False,
                f"Session duration cannot exceed {self.MAX_DURATION_HOURS} hours "
                f"({self.MAX_DURATION_HOURS // 24} days).",
            )
        return (True, None)

    def get_inactive_sessions(
        self, sessions: list[Session], inactive_threshold_hours: int = 72
    ) -> list[Session]:
        """Identify sessions that have been inactive for too long.

        Args:
            sessions: List of sessions to evaluate.
            inactive_threshold_hours: Hours of inactivity threshold.

        Returns:
            List of sessions exceeding the inactivity threshold.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=inactive_threshold_hours)
        return [s for s in sessions if s.is_active and (
            s.last_activity is None or s.last_activity < cutoff
        )]

    def __repr__(self) -> str:
        return (
            f"<SessionPolicy "
            f"max_sessions={self.MAX_CONCURRENT_SESSIONS} "
            f"duration={self.DEFAULT_DURATION_HOURS}h>"
        )
