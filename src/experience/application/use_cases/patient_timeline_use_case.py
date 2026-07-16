"""Experience Engine — Patient Timeline Use Case.

Builds a chronological timeline of all events in the patient's journey:
  Register → Queue (Waiting) → Called → In Progress → Completed → Report Ready → Delivered

Edge cases: Cancelled, No Show, Multiple Visits.

Data source: QueueEntry domain entities (each stores lifecycle timestamps).
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result


# ── Event type constants ──────────────────────────────────────────────────────

EVENT_TYPES = {
    "registered": {
        "label": "Registered",
        "label_hi": "पंजीकृत",
        "icon": "📝",
        "color": "#9e9e9e",
    },
    "waiting": {
        "label": "Waiting in Queue",
        "label_hi": "कतार में प्रतीक्षा",
        "icon": "⏳",
        "color": "#f9a825",
    },
    "called": {
        "label": "Called",
        "label_hi": "बुलाया गया",
        "icon": "🔵",
        "color": "#1e88e5",
    },
    "recalled": {
        "label": "Recalled",
        "label_hi": "पुनः बुलाया गया",
        "icon": "🔁",
        "color": "#1e88e5",
    },
    "in_progress": {
        "label": "Test Started",
        "label_hi": "परीक्षण शुरू",
        "icon": "🟠",
        "color": "#ef6c00",
    },
    "completed": {
        "label": "Completed",
        "label_hi": "पूर्ण",
        "icon": "✅",
        "color": "#43a047",
    },
    "report_ready": {
        "label": "Report Ready",
        "label_hi": "रिपोर्ट तैयार",
        "icon": "📋",
        "color": "#8e24aa",
    },
    "delivered": {
        "label": "Report Delivered",
        "label_hi": "रिपोर्ट दी गई",
        "icon": "📄",
        "color": "#00897b",
    },
    "cancelled": {
        "label": "Cancelled",
        "label_hi": "रद्द",
        "icon": "❌",
        "color": "#e53935",
    },
    "no_show": {
        "label": "No Show",
        "label_hi": "उपस्थित नहीं",
        "icon": "🚫",
        "color": "#757575",
    },
}

# Mapping from QueueEntry status value → event type
STATUS_TO_EVENT = {
    "WAITING": "waiting",
    "CALLED": "called",
    "IN_PROGRESS": "in_progress",
    "COMPLETED": "completed",
    "REPORT_READY": "report_ready",
    "DELIVERED": "delivered",
    "CANCELLED": "cancelled",
    "NO_SHOW": "no_show",
}


class PatientTimelineUseCase(BaseUseCase):
    """Use case for building a patient's journey timeline.

    Reads all queue entries for a patient and derives a chronological
    list of events from their timestamp fields.
    """

    def __init__(self, queue_repo) -> None:
        super().__init__()
        self._queue_repo = queue_repo

    async def authorize(self, command: Command) -> None:
        """Timeline requires patient authentication (handled by route DI)."""
        pass

    async def execute(self, command: Command) -> Result:
        """Build the patient's timeline.

        Args:
            command: Data with patient_uuid.

        Returns:
            Result with timeline data.
        """
        patient_uuid = command.data.get("patient_uuid")
        if not patient_uuid:
            return Result.fail(error="patient_uuid is required.")

        # Get all queue entries for this patient (active + historical)
        try:
            entries = await self._queue_repo.list_patient_queue(patient_uuid)
        except Exception as e:
            return Result.fail(error=f"Failed to fetch queue entries: {e}")

        if not entries:
            return Result.ok(
                data={
                    "patient_uuid": patient_uuid,
                    "total_events": 0,
                    "visits": [],
                    "all_events": [],
                },
                message="No queue entries found for this patient.",
            )

        # Build events from each entry
        all_events: list[dict] = []
        visit_map: dict[str, dict] = {}

        for entry in entries:
            visit_id = entry.visit_id
            service_name = entry.service_name
            service_code = entry.service_code
            token_number = entry.token_number
            room = entry.room
            status_value = entry.status.value if entry.status else "WAITING"

            # Initialize visit group
            if visit_id not in visit_map:
                visit_map[visit_id] = {
                    "visit_id": visit_id,
                    "services": set(),
                    "total_tests": 0,
                    "events": [],
                }
            visit_map[visit_id]["services"].add(service_name)
            visit_map[visit_id]["total_tests"] += 1

            # Derive events from timestamp fields
            # Each non-None timestamp becomes a timeline event
            entry_events = []

            # created_at → "registered" (queue entry creation)
            if entry.created_at:
                entry_events.append({
                    "type": "registered",
                    "timestamp": self._format_dt(entry.created_at),
                    "service_name": service_name,
                    "service_code": service_code,
                    "token_number": token_number,
                    "room": room,
                    "visit_id": visit_id,
                })

            # called_at → "called"
            if entry.called_at:
                entry_events.append({
                    "type": "called",
                    "timestamp": self._format_dt(entry.called_at),
                    "service_name": service_name,
                    "service_code": service_code,
                    "token_number": token_number,
                    "room": room,
                    "visit_id": visit_id,
                })

            # started_at → "in_progress"
            if entry.started_at:
                entry_events.append({
                    "type": "in_progress",
                    "timestamp": self._format_dt(entry.started_at),
                    "service_name": service_name,
                    "service_code": service_code,
                    "token_number": token_number,
                    "room": room,
                    "visit_id": visit_id,
                })

            # completed_at → "completed"
            if entry.completed_at:
                entry_events.append({
                    "type": "completed",
                    "timestamp": self._format_dt(entry.completed_at),
                    "service_name": service_name,
                    "service_code": service_code,
                    "token_number": token_number,
                    "room": room,
                    "visit_id": visit_id,
                })

            # report_ready_at → "report_ready"
            if entry.report_ready_at:
                entry_events.append({
                    "type": "report_ready",
                    "timestamp": self._format_dt(entry.report_ready_at),
                    "service_name": service_name,
                    "service_code": service_code,
                    "token_number": token_number,
                    "room": room,
                    "visit_id": visit_id,
                })

            # delivered_at → "delivered"
            if entry.delivered_at:
                entry_events.append({
                    "type": "delivered",
                    "timestamp": self._format_dt(entry.delivered_at),
                    "service_name": service_name,
                    "service_code": service_code,
                    "token_number": token_number,
                    "room": room,
                    "visit_id": visit_id,
                })

            # If status is CANCELLED or NO_SHOW but no specific timestamp,
            # use updated_at as the event time
            if status_value == "CANCELLED":
                entry_events.append({
                    "type": "cancelled",
                    "timestamp": self._format_dt(entry.updated_at or entry.created_at),
                    "service_name": service_name,
                    "service_code": service_code,
                    "token_number": token_number,
                    "room": room,
                    "visit_id": visit_id,
                })
            elif status_value == "NO_SHOW":
                entry_events.append({
                    "type": "no_show",
                    "timestamp": self._format_dt(entry.updated_at or entry.created_at),
                    "service_name": service_name,
                    "service_code": service_code,
                    "token_number": token_number,
                    "room": room,
                    "visit_id": visit_id,
                })

            # Sort entry events chronologically
            entry_events.sort(key=lambda e: e["timestamp"])
            visit_map[visit_id]["events"].extend(entry_events)
            all_events.extend(entry_events)

        # Sort all events chronologically
        all_events.sort(key=lambda e: e["timestamp"])

        # Build visits array
        visits = []
        for vid in sorted(visit_map.keys()):
            v = visit_map[vid]
            v_events = sorted(v["events"], key=lambda e: e["timestamp"])
            visits.append({
                "visit_id": vid,
                "total_tests": v["total_tests"],
                "services": sorted(list(v["services"])),
                "events": v_events,
            })

        # Reverse visits so most recent is first
        visits.reverse()

        return Result.ok(
            data={
                "patient_uuid": patient_uuid,
                "total_events": len(all_events),
                "visits": visits,
                "all_events": all_events,
            },
            message=f"Timeline built with {len(all_events)} events across {len(visits)} visit(s).",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_dt(dt: datetime | None) -> str:
        """Format a datetime as ISO 8601 string.

        Args:
            dt: Datetime to format.

        Returns:
            ISO 8601 string, or empty string if dt is None.
        """
        if dt is None:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
