"""Queue domain events — constants for audit and event sourcing.

Each constant maps to a human-readable queue action name used in
audit logs, notifications, and domain event publishing.
"""

# ── Queue Entry Lifecycle Events ────────────────────────────────────────
QUEUE_CREATED = "QUEUE_CREATED"           # Reception registers patient for test(s)
QUEUE_CALLED = "QUEUE_CALLED"             # Technician calls patient to room
QUEUE_RECALLED = "QUEUE_RECALLED"         # Send patient back to waiting
QUEUE_STARTED = "QUEUE_STARTED"           # Test is in progress
QUEUE_COMPLETED = "QUEUE_COMPLETED"       # Test completed
QUEUE_REPORT_READY = "QUEUE_REPORT_READY"  # Report is available
QUEUE_DELIVERED = "QUEUE_DELIVERED"       # Report delivered to patient
QUEUE_CANCELLED = "QUEUE_CANCELLED"       # Cancelled (with reason)
QUEUE_NO_SHOW = "QUEUE_NO_SHOW"           # Patient didn't respond
QUEUE_ALERT = "QUEUE_ALERT"               # Technician sent alert/reminder to patient

# ── Human-readable labels ───────────────────────────────────────────────
EVENT_LABELS = {
    QUEUE_CREATED: "Created Queue Entry",
    QUEUE_CALLED: "Called Patient",
    QUEUE_RECALLED: "Sent Back to Waiting",
    QUEUE_STARTED: "Started Test",
    QUEUE_COMPLETED: "Completed Test",
    QUEUE_REPORT_READY: "Marked Report Ready",
    QUEUE_DELIVERED: "Delivered Report",
    QUEUE_CANCELLED: "Cancelled",
    QUEUE_NO_SHOW: "Marked No-Show",
    QUEUE_ALERT: "Alerted Patient",
}

# ── Map status -> event name ────────────────────────────────────────────
STATUS_TO_EVENT = {
    "WAITING": QUEUE_CREATED,
    "CALLED": QUEUE_CALLED,
    "IN_PROGRESS": QUEUE_STARTED,
    "COMPLETED": QUEUE_COMPLETED,
    "REPORT_READY": QUEUE_REPORT_READY,
    "DELIVERED": QUEUE_DELIVERED,
    "CANCELLED": QUEUE_CANCELLED,
    "NO_SHOW": QUEUE_NO_SHOW,
}
