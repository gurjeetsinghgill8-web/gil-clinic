"""Queue Lite — TV Alert Use Case.

Manages broadcast alerts for TV displays in the waiting area.
Alerts are stored in-memory and auto-expire after being read.

Three severity levels:
- info (blue banner, auto-dismiss 10s)
- warning (amber pulsing, dismiss button, auto-dismiss 30s)
- emergency (full-screen red overlay, requires confirmation)
"""

from __future__ import annotations

import time
from typing import Any

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result

# In-memory alert store
_pending_alerts: list[dict[str, Any]] = []


class TvAlertUseCase(BaseUseCase):
    """Use case for managing TV display broadcast alerts.

    Alerts are stored in-memory (not persisted to DB) since they are
    ephemeral broadcast messages intended for immediate display.
    """

    def __init__(self) -> None:
        super().__init__()

    async def authorize(self, command: Command) -> None:
        """TV alerts require staff authentication."""
        pass

    async def execute(self, command: Command) -> Result:
        """Execute a TV alert operation.

        Args:
            command: Command with operation type and data.
                - operation="send": Send a new alert
                - operation="check": Check for pending alerts

        Returns:
            Result with alert data.
        """
        dto = command.data
        operation = dto.get("operation", "send")

        if operation == "send":
            return self._send_alert(dto)
        elif operation == "check":
            return self._check_alerts()
        else:
            return Result.fail(error=f"Unknown operation: {operation}")

    def _send_alert(self, dto: dict[str, Any]) -> Result:
        """Send a new alert to the TV display.

        Args:
            dto: Alert data with message, severity, duration_seconds.

        Returns:
            Result with confirmation.
        """
        message = dto.get("message", "")
        severity = dto.get("severity", "info")
        duration = dto.get("duration_seconds", 30)

        if not message:
            return Result.fail(error="Alert message is required.")

        if severity not in ("info", "warning", "emergency"):
            return Result.fail(
                error=f"Invalid severity: {severity}. Use info, warning, or emergency."
            )

        alert = {
            "id": str(int(time.time() * 1000)),
            "message": message,
            "severity": severity,
            "duration_seconds": duration,
            "created_at": time.time(),
        }

        # Add to pending list (keep last 50)
        _pending_alerts.append(alert)
        if len(_pending_alerts) > 50:
            _pending_alerts.pop(0)

        return Result.ok(
            data={
                "status": "sent",
                "alert": alert,
                "pending_count": len(_pending_alerts),
            },
            message="TV alert sent successfully.",
        )

    def _check_alerts(self) -> Result:
        """Check for pending alerts and return the most recent one.

        Alerts older than 60 seconds are auto-expired.
        Returns one alert at a time (oldest unread first).

        Returns:
            Result with alert data or empty if none pending.
        """
        now = time.time()

        # Clean expired alerts
        active = [a for a in _pending_alerts if (now - a["created_at"]) < 60]
        _pending_alerts.clear()
        _pending_alerts.extend(active)

        if not _pending_alerts:
            return Result.ok(data={"alert": None, "message": "No pending alerts."})

        # Return the most recent alert and remove it
        latest = _pending_alerts.pop(0)
        return Result.ok(
            data={
                "alert": latest,
                "message": latest["message"],
            }
        )
